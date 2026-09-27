/** @odoo-module **/

import { ErrorDialog, RPCErrorDialog } from "@web/core/errors/error_dialogs";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

/**
 * Copy error details in both secure and insecure browser contexts.
 *
 * navigator.clipboard is unavailable on the HTTP URL used by some Utility ERP
 * deployments. Keep the Odoo error dialog usable there without changing the
 * error reporting contract.
 */
async function copyText(text) {
    const clipboard = browser.navigator && browser.navigator.clipboard;
    if (clipboard && typeof clipboard.writeText === "function") {
        try {
            await clipboard.writeText(text);
            return;
        } catch (_error) {
            // Fall through to the legacy copy path when permissions deny access.
        }
    }

    if (!document.body || typeof document.execCommand !== "function") {
        browser.console.warn("Unable to copy the Odoo error details to the clipboard.");
        return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand("copy");
    } finally {
        document.body.removeChild(textarea);
    }
}

patch(ErrorDialog.prototype, "utility_core.error_dialog_clipboard", {
    onClickClipboard() {
        return copyText(`${this.props.name}\n${this.props.message}\n${this.props.traceback}`);
    },
});

patch(RPCErrorDialog.prototype, "utility_core.rpc_error_dialog_clipboard", {
    onClickClipboard() {
        return copyText(`${this.props.name}\n${this.props.message}\n${this.traceback}`);
    },
});
