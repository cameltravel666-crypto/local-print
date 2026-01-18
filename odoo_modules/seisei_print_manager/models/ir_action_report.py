import threading
from time import time

from odoo import _, api, exceptions, fields, models, registry
from odoo.tools.safe_eval import safe_eval

REPORT_TYPES = {"qweb-pdf": "pdf", "qweb-text": "text"}


class IrActionsReport(models.Model):
    """
    Inherit ir.actions.report, add printer related fields
    """
    _inherit = "ir.actions.report"

    @api.model
    def get_report_policy(self, report_name):
        """
        Returns if the action is a direct print or pdf
        Called from js
        """
        report = self._get_report_from_name(report_name)
        if not report:
            return {}
        
        policy = report.get_print_policy()
        result = {
            "action": policy["action"],
            "printer_id": policy["printer_id"],
        }

        if result["action"] == "print" and not policy["printer_id"]:
            result["exception"] = 'No printer configured to print this report.'

        if result["action"] == "print" and policy.get('printer_id'):
            printer = self.env['seisei.printer'].browse(policy['printer_id'])
            if printer.status in ['error', 'server-error', 'unavailable', 'unknown']:
                result["exception"] = 'Printer is not available.'

        if result.get("exception", None) is not None:
            return result

        # special case
        if self.env.context.get("print_action"):
            result["action"] = self.env.context.get("print_action")

        return result

    def get_print_policies(self):
        """
        Get all available print policies for the report
        Returns a list of policy options for user selection
        """
        self.ensure_one()
        if self.env.context.get("just_download"):
            return [{
                "id": None,
                "name": _("Download Only"),
                "action_type": "download",
                "printer_id": None,
                "printer_name": None,
            }]
        
        policies = []
        mappings = self.env['seisei.report.mapping'].get_mappings(self.id)
        if mappings:
            for mapping in mappings:
                policy = mapping.get_print_policy()
                policy['id'] = mapping.id
                policy['name'] = mapping.display_name or mapping.name
                policy['printer_name'] = mapping.printer_name
                policies.append(policy)

        # Add user default policy if no mappings found
        if not policies:
            user_policy = self.env.user.get_print_policy()
            if user_policy:
                user_policy['id'] = None
                user_policy['name'] = _("User Default")
                user_policy['printer_name'] = self.env.user.default_printer_id.name if self.env.user.default_printer_id else None
                policies.append(user_policy)

        # Add global default policy as fallback
        if not policies:
            global_policy = self.env['res.config.settings'].get_print_policy()
            if global_policy:
                global_policy['id'] = None
                global_policy['name'] = _("Global Default")
                global_policy['printer_name'] = None
                policies.append(global_policy)

        return policies

    def print_to_printer(self, data=None, mapping_id=None):
        """
        Print the document with specified mapping
        
        Args:
            record_ids: Record IDs to print
            data: Additional data
            mapping_id: Selected mapping ID (optional)
        """
        # Get policy from mapping if provided
        if mapping_id:
            mapping = self.env['seisei.report.mapping'].browse(mapping_id)
            if not mapping.exists():
                raise exceptions.UserError(_("Invalid mapping selected."))
            policy = mapping.get_print_policy()
        else:
            raise exceptions.UserError(_("No mapping selected."))
            
        printer_id = policy.get("printer_id", None)
        printer = self.env['seisei.printer'].browse(printer_id)
        if not printer:
            raise exceptions.UserError(_("No printer configured to print this report."))
        
        if printer.status in ['error', 'server-error', 'unavailable', 'unknown']:
            raise exceptions.UserError(_("Printer is not available."))

        return self.print_document(data=data, policy=policy)

    def print_document(self, data=None, policy=None):
        """
        Print a document, do not return the document file
        """
        report_type = REPORT_TYPES.get(self.report_type)
        if not report_type:
            raise exceptions.UserError(
                _("This report type (%s) is not supported by direct printing!")
                % str(self.report_type)
            )

        record_ids = self.env.context.get("active_ids") or []
        if not record_ids:
            raise exceptions.UserError(_("No record IDs found."))

        method_name = f"_render_qweb_{report_type}"
        document, doc_format = getattr(
            self.with_context(skip_send_to_printer=True, policy=policy), method_name
        )(self.report_name, record_ids, data=data)

        printer_id = policy.get("printer_id", None)
        printer = self.env['seisei.printer'].browse(printer_id)
        if not printer:
            raise exceptions.UserError(_("No printer configured to print this report."))
   
        policy["title"] = self.report_name
        policy["res_ids"] = record_ids

        return printer.print_document(
            self, document, doc_format=self.report_type, **policy
        )

    def _can_print_report(self, policy, printer, document):
        """
        Predicate that decide if report can be sent to printer
        If you want to prevent `render_qweb_pdf` to send report you can set
        the `must_skip_send_to_printer` key to True in the context
        """
        if self.env.context.get("just_download"):
            return False
        if (
            (policy["action"] == "print" \
             or policy["action"] == "download_after_print")
            and printer
            and document
            and not policy.get("exception")
        ):
            return True
        return False

    def report_action(self, docids, data=None, config=True):
        res = super().report_action(docids, data=data, config=config)
        if not res.get("id"):
            res["id"] = self.id
        return res

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """
        Generate a PDF and returns it.
        If the action configured on the report is server, it prints the
        generated document as well.
        """
        document, doc_format = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
        report = self._get_report(report_ref)

        policy = self.env.context.get("policy")
        if policy:
            printer_id = policy.get("printer_id", None)
            printer = self.env['seisei.printer'].browse(printer_id)

            if not self.env.context.get("skip_send_to_printer"):
                can_print_report = report._can_print_report(policy, printer, document)
                if can_print_report:
                    printer.print_document(
                        report, document, doc_format=report.report_type, **policy
                    )

        return document, doc_format

    def _render_qweb_text(self, report_ref, docids, data=None):
        """
        Generate a TEXT file and returns it.
        If the action configured on the report is server, it prints the
        generated document as well.
        """
        document, doc_format = super()._render_qweb_text(
            report_ref, docids=docids, data=data
        )
        report = self._get_report(report_ref)
        policy = self.env.context.get("policy")

        if policy:
            printer_id = policy.get("printer_id", None)
            printer = self.env['seisei.printer'].browse(printer_id)

            if not self.env.context.get("skip_send_to_printer"):
                can_print_report = report._can_print_report(policy, printer, document)
                if can_print_report:
                    printer.print_document(
                        report, document, doc_format=report.report_type, **policy
                    )

        return document, doc_format
