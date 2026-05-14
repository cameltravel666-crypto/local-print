/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * POS 打印任务消费者
 * 
 * 功能：
 * 1. 轮询待打印任务
 * 2. 认领任务并调用 YLHC Recorder 打印
 * 3. 回写状态到 Odoo
 * 4. 显示调试面板（debug=1）
 */
export class PosPrintConsumer extends Component {
    setup() {
        this.state = useState({
            jobs: [],
            isPolling: false,
            lastPollTime: null,
            error: null,
            clientId: this._generateClientId(),
            ylhcRecorderUrl: null,
            ylhcRecorderToken: null,
        });

        // 从系统参数或配置中获取 YLHC Recorder 信息
        this._loadYlhcConfig();

        // 启动轮询
        this.pollInterval = null;
        this.startPolling();

        onMounted(() => {
            console.log('[POS Print Consumer] Initialized');
        });

        onWillUnmount(() => {
            this.stopPolling();
        });
    }

    /**
     * 生成客户端标识
     */
    _generateClientId() {
        // 使用浏览器信息 + 时间戳生成唯一标识
        const userAgent = navigator.userAgent;
        const timestamp = Date.now();
        return `${userAgent.substring(0, 20)}-${timestamp}`;
    }

    /**
     * 加载 YLHC Recorder 配置
     */
    async _loadYlhcConfig() {
        try {
            // 从系统参数获取配置
            const result = await rpc("/web/dataset/call_kw", {
                model: "ir.config_parameter",
                method: "get_param",
                args: [],
                kwargs: {
                    key: "pos_print.ylhc_recorder_url",
                    default: "http://127.0.0.1:8868/print"
                }
            });
            this.state.ylhcRecorderUrl = result || "http://127.0.0.1:8868/print";

            // 获取 token（如果有）
            const tokenResult = await rpc("/web/dataset/call_kw", {
                model: "ir.config_parameter",
                method: "get_param",
                args: [],
                kwargs: {
                    key: "pos_print.ylhc_recorder_token",
                    default: ""
                }
            });
            this.state.ylhcRecorderToken = tokenResult || "";
        } catch (error) {
            console.error('[POS Print Consumer] Failed to load YLHC config:', error);
            this.state.ylhcRecorderUrl = "http://127.0.0.1:8868/print";
        }
    }

    /**
     * 启动轮询
     */
    startPolling() {
        if (this.pollInterval) {
            return;
        }

        this.state.isPolling = true;
        
        // 立即执行一次
        this._pollPendingJobs();

        // 每 2-3 秒轮询一次
        this.pollInterval = setInterval(() => {
            this._pollPendingJobs();
        }, 2500);

        console.log('[POS Print Consumer] Polling started');
    }

    /**
     * 停止轮询
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
            this.state.isPolling = false;
            console.log('[POS Print Consumer] Polling stopped');
        }
    }

    /**
     * 轮询待打印任务
     */
    async _pollPendingJobs() {
        try {
            const posConfig = this.env.pos?.config;
            if (!posConfig) {
                console.warn('[POS Print Consumer] No POS config available');
                return;
            }

            // 调用 API 获取待打印任务
            const result = await rpc("/pos/print_jobs/pending", {
                config_id: posConfig.id,
                limit: 10
            });

            if (result.success && result.jobs && result.jobs.length > 0) {
                console.log(`[POS Print Consumer] Found ${result.jobs.length} pending jobs`);
                
                // 处理每个任务
                for (const jobData of result.jobs) {
                    await this._processJob(jobData);
                }
            }

            this.state.lastPollTime = new Date();
            this.state.error = null;

        } catch (error) {
            console.error('[POS Print Consumer] Poll error:', error);
            this.state.error = error.message || 'Poll failed';
        }
    }

    /**
     * 处理单个打印任务
     */
    async _processJob(jobData) {
        try {
            console.log(`[POS Print Consumer] Processing job ${jobData.name}`);

            // 1. 认领任务（原子操作）
            const claimResult = await rpc("/pos/print_jobs/claim", {
                job_id: jobData.id,
                client_id: this.state.clientId
            });

            if (!claimResult.success) {
                console.warn(`[POS Print Consumer] Failed to claim job ${jobData.name}: ${claimResult.message}`);
                return; // 任务已被其他客户端认领
            }

            const claimedJob = claimResult.job;
            console.log(`[POS Print Consumer] Job ${claimedJob.name} claimed successfully`);

            // 2. 调用 YLHC Recorder 打印
            const printSuccess = await this._callYlhcRecorder(claimedJob);

            // 3. 回写状态
            if (printSuccess) {
                await rpc("/pos/print_jobs/mark_done", {
                    job_id: claimedJob.id
                });
                console.log(`[POS Print Consumer] Job ${claimedJob.name} marked as done`);
            } else {
                await rpc("/pos/print_jobs/mark_failed", {
                    job_id: claimedJob.id,
                    error_message: 'YLHC Recorder print failed'
                });
                console.error(`[POS Print Consumer] Job ${claimedJob.name} marked as failed`);
            }

        } catch (error) {
            console.error(`[POS Print Consumer] Failed to process job ${jobData.name}:`, error);
            
            // 标记失败
            try {
                await rpc("/pos/print_jobs/mark_failed", {
                    job_id: jobData.id,
                    error_message: error.message || 'Unknown error'
                });
            } catch (markError) {
                console.error('[POS Print Consumer] Failed to mark job as failed:', markError);
            }
        }
    }

    /**
     * 调用 YLHC Recorder 打印
     * 
     * @param {Object} job - 打印任务数据
     * @returns {Promise<boolean>} - 打印是否成功
     */
    async _callYlhcRecorder(job) {
        try {
            const url = this.state.ylhcRecorderUrl;
            const payload = job.print_payload;

            console.log(`[POS Print Consumer] Calling YLHC Recorder: ${url}`);
            console.log('[POS Print Consumer] Payload:', payload);

            // 准备请求头
            const headers = {
                'Content-Type': 'application/json',
            };

            if (this.state.ylhcRecorderToken) {
                headers['Authorization'] = `Bearer ${this.state.ylhcRecorderToken}`;
            }

            // 发送打印请求
            const response = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            console.log('[POS Print Consumer] YLHC Recorder response:', result);

            // 根据 YLHC Recorder 的响应格式判断是否成功
            // TODO: 根据实际 YLHC Recorder 的响应格式调整
            return result.success !== false;

        } catch (error) {
            console.error('[POS Print Consumer] YLHC Recorder call failed:', error);
            return false;
        }
    }

    /**
     * 刷新任务状态（用于调试面板）
     */
    async refreshJobStatus() {
        try {
            const posConfig = this.env.pos?.config;
            if (!posConfig) {
                return;
            }

            const result = await rpc("/pos/print_jobs/status", {
                config_id: posConfig.id,
                limit: 20
            });

            if (result.success) {
                this.state.jobs = result.jobs;
            }
        } catch (error) {
            console.error('[POS Print Consumer] Failed to refresh job status:', error);
        }
    }

    /**
     * 重试失败的任务
     */
    async retryJob(jobId) {
        try {
            const result = await rpc("/pos/print_jobs/retry", {
                job_id: jobId
            });

            if (result.success) {
                console.log(`[POS Print Consumer] Job ${jobId} retried`);
                await this.refreshJobStatus();
            } else {
                console.error(`[POS Print Consumer] Failed to retry job ${jobId}:`, result.message);
            }
        } catch (error) {
            console.error('[POS Print Consumer] Retry error:', error);
        }
    }

    /**
     * 检查是否显示调试面板
     */
    get showDebugPanel() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('debug') === '1' || urlParams.get('debug') === 'true';
    }
}

// 注册到 POS 扩展点
registry.category("pos_extensions").add("pos_print_consumer", {
    component: PosPrintConsumer,
});


