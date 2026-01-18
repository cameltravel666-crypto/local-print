import {_t} from "@web/core/l10n/translation";
import {markup} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {FormViewDialog} from "@web/views/view_dialogs/form_view_dialog";


async function SeiseiReportActionHandler(action, options, env) {
    if (action.report_type === "qweb-pdf") {
        const orm = env.services.orm;

        // Get print policies
        const policies = await orm.call(
            "ir.actions.report",
            "get_print_policies",
            [action.id], {
                context: {
                    just_download: action.context.just_download
                }
            }
        );

        let selectedPolicy = null;
        let policyId = null;

        // If multiple policies exist, open wizard to let user choose
        if (policies.length > 1) {
            // Close the old dialog/wizard
            await env.services.action.doAction({ type: "ir.actions.act_window_close" });

            // Use FormViewDialog to get user selection
            const dialogResult = await new Promise((resolve) => {
                env.services.dialog.add(FormViewDialog, {
                    resModel: 'seisei.print.policy.selector.wizard',
                    title: _t('Select Print Policy'),
                    context: {
                        ...action.context,
                        default_report_id: action.id,
                        policies: policies,
                    },
                    onRecordSaved: async (record) => {
                        let policy_ids = record.data.policy_ids.records;
                        let selected_policy_id = null;
                        policy_ids.forEach(policy => {
                            if (policy.data.is_selected) {
                                selected_policy_id = policy.data.mapping_id[0];
                            }
                        });

                        resolve({
                            canceled: false,
                            policyId: selected_policy_id,
                            data: record.data.data,
                        });
                    },
                    onRecordDiscarded: () => {
                        resolve({ canceled: true });
                    },
                });
            });

            if (dialogResult.canceled) {
                return true;
            }

            // Get the selected mapping ID
            policyId = dialogResult.policyId;
            if (!policyId) {
                env.services.notification.add(_t("Please select a print policy"), {
                    type: "warning",
                });
                return true;
            }

            // Get policy from selected mapping
            const selectedLine = policies.find(p => p.id === policyId);
            if (selectedLine) {
                selectedPolicy = selectedLine;
            }
        } else if (policies.length === 1) {
            selectedPolicy = policies[0];
            policyId = policies[0].id;
        } else {
            // No policies available, fallback to download
            env.services.notification.add(_t("No print policies configured, downloading instead."), {
                type: "warning",
            });
            return false;
        }

        let exception = selectedPolicy?.exception;
        if (!exception && ['print', 'download_after_print'].includes(selectedPolicy?.action_type)) {
            const result = await orm.call(
                "ir.actions.report",
                "print_to_printer",
                [action.id], {
                    data: action.data,
                    mapping_id: policyId,
                    context: action.context
                }
            );

            // Close current dialog/wizard
            await env.services?.action?.doAction({ type: "ir.actions.act_window_close" });

            debugger
            if (result) {
                env.services.notification.add(_t("Successfully sent to printer!"), {
                    type: "success",
                });

                if (selectedPolicy.action_type === 'download_after_print') {
                    return false;
                } else {
                    return true;
                }
            } else {
                env.services.notification.add(_t("Could not send to printer!"), {
                    type: "danger",
                });
                exception = true;
                if (selectedPolicy.action_type === 'download_after_print') {
                    return false;
                }
            }
        }
        
        if (exception) {
            const params = {
                the_report: _t("The report"),
                couldnt_be_printed: _t(
                    "Couldn't be printed. Click on the button below to download it!"
                ),
                failed_to_print: _t("Failed to print on"),
            };
            const remove = env.services.notification.add(
                markup(
                    `<p>${params.the_report} <strong>${action.name}</strong> ${params.couldnt_be_printed}</p>`
                ),
                {
                    title: `${params.failed_to_print} ${selectedPolicy.printer_name || 'Unknown'}`,
                    type: "warning",
                    sticky: true,
                    messageIsHtml: true,
                    buttons: [
                        {
                            name: _t("Download"),
                            primary: true,
                            icon: "fa-download",
                            onClick: async () => {
                                const context = {
                                    just_download: true,
                                };
                                await env.services.action.doAction(
                                    {type: "ir.actions.report", ...action}, {
                                        additionalContext: context,
                                    }
                                );
                                remove();
                            }
                        }
                    ]
                }
            );

            return true;
        }
    }
}


registry
    .category("ir.actions.report handlers")
    .add("seisei_report_action_handler", SeiseiReportActionHandler);
