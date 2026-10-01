/** @odoo-module **/

import { registry } from "@web/core/registry";
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
        this.readerId = `reader_${this.props.record.resModel}_${this.props.name}_${this.props.record.resId || 'new'}`;

        onWillUnmount(() => {
            this.stopScanning();
        });
    }

    startScanning() {
        this.state.isScanning = true;
        this.state.errorMessage = false;
        
        // Wait for DOM to render the reader div
        setTimeout(() => {
            try {
                this.html5QrcodeScanner = new Html5Qrcode(this.readerId);
                this.html5QrcodeScanner.start(
                    { facingMode: "environment" },
                    { fps: 10, qrbox: {width: 250, height: 250} },
                    (decodedText, decodedResult) => {
                        // Success
                        this.props.update(decodedText);
                        this.stopScanning();
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

registry.category("fields").add("barcode_camera", BarcodeCameraWidget);
