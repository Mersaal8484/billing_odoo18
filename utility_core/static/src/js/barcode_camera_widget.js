/** @odoo-module **/

import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { CharField } from "@web/views/fields/char/char_field";
import { onWillUnmount, useState } from "@odoo/owl";

export class BarcodeCameraWidget extends CharField {
    setup() {
        super.setup();
        this.state = useState({
            isScanning: false,
            errorMessage: false,
        });
        this.html5QrcodeScanner = null;
        this.scannerStartTimeout = null;
        this.readerId = `reader_${this.props.record.resModel}_${this.props.name}_${this.props.record.resId || 'new'}`;

        onWillUnmount(() => {
            if (this.scannerStartTimeout) {
                clearTimeout(this.scannerStartTimeout);
                this.scannerStartTimeout = null;
            }
            this.stopScanning();
        });
    }

    async startScanning() {
        this.state.isScanning = true;
        this.state.errorMessage = false;
        await loadJS("/utility_core/static/src/js/lib/html5-qrcode.min.js");
        
        // Wait for DOM to render the reader div
        this.scannerStartTimeout = setTimeout(() => {
            this.scannerStartTimeout = null;
            try {
                this.html5QrcodeScanner = new Html5Qrcode(this.readerId);
                this.html5QrcodeScanner.start(
                    { facingMode: "environment" },
                    { fps: 10, qrbox: {width: 250, height: 250} },
                    async (decodedText) => {
                        try {
                            await this.props.record.update({ [this.props.name]: decodedText });
                            this.stopScanning();
                        } catch (error) {
                            console.error("Unable to apply scanned value:", error);
                            this.state.errorMessage = error.message || "تعذر حفظ قيمة الباركود.";
                        }
                    },
                    (errorMessage) => {
                        // Ignore standard scan errors (happens when no barcode found)
                    }
                ).catch(err => {
                    console.error("Camera error:", err);
                    this.state.errorMessage = "تعذر الوصول للكاميرا. تأكد من إعطاء الصلاحيات أو استخدام اتصال آمن (HTTPS).";
                });
            } catch (e) {
                console.error("Scanner init error:", e);
                this.state.errorMessage = "حدث خطأ في التهيئة.";
            }
        }, 100);
    }

    stopScanning() {
        if (this.html5QrcodeScanner && this.state.isScanning) {
            this.html5QrcodeScanner.stop().then(() => {
                this.html5QrcodeScanner.clear();
                this.html5QrcodeScanner = null;
                this.state.isScanning = false;
            }).catch(err => {
                console.error("Stop error:", err);
                this.html5QrcodeScanner = null;
                this.state.isScanning = false;
            });
        } else {
            this.state.isScanning = false;
        }
    }
}

BarcodeCameraWidget.template = "utility_core.BarcodeCameraWidget";
BarcodeCameraWidget.components = {
    ...CharField.components,
};

registry.category("fields").add("barcode_camera", {
    component: BarcodeCameraWidget,
    supportedTypes: ["char"],
});
