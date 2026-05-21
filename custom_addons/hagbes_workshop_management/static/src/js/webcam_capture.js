/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useRef, onMounted } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class WebcamCapture extends Component {
    setup() {
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");

        onMounted(() => {
            if (navigator.mediaDevices?.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: true })
                    .then(stream => {
                        this.videoRef.el.srcObject = stream;
                        this.videoRef.el.play();
                    })
                    .catch(err => console.error("Webcam error:", err));
            }
        });
    }

    capture() {
        const context = this.canvasRef.el.getContext("2d");
        context.drawImage(this.videoRef.el, 0, 0, 320, 240);
        const dataUrl = this.canvasRef.el.toDataURL("image/png");
        this.props.update(dataUrl.split(",")[1]);  // store in binary field
    }
}

WebcamCapture.props = {
    ...standardFieldProps,
};

WebcamCapture.template = "workshop_management.WebcamCapture"; // must match XML t-name
registry.category("fields").add("webcam_capture", WebcamCapture);
