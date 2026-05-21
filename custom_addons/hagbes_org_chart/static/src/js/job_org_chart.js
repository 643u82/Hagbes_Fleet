/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class JobOrgChart extends Component {
    setup() {
        this.chartContainerRef = useRef("chartContainer");

        onMounted(() => {
            const container = this.chartContainerRef.el;
            const chart = container.querySelector(".org-chart-root");

            let isDragging = false;
            let startX = 0, startY = 0;
            let currentX = 0, currentY = 0;

            container.style.cursor = "grab";

            container.addEventListener("mousedown", (e) => {
                isDragging = true;
                startX = e.clientX - currentX;
                startY = e.clientY - currentY;
                container.style.cursor = "grabbing";
            });

            container.addEventListener("mouseup", () => {
                isDragging = false;
                container.style.cursor = "grab";
            });

            container.addEventListener("mouseleave", () => {
                isDragging = false;
                container.style.cursor = "grab";
            });

            container.addEventListener("mousemove", (e) => {
                if (!isDragging) return;
                e.preventDefault();
                currentX = e.clientX - startX;
                currentY = e.clientY - startY;
                chart.style.transform = `translate(${currentX}px, ${currentY}px)`;
            });

            // Center the chart initially
            setTimeout(() => {
                const containerWidth = container.clientWidth;
                const chartWidth = chart.clientWidth;

                currentX = (containerWidth - chartWidth) / 2;
                currentY = 40;
                chart.style.transform = `translate(${currentX}px, ${currentY}px)`;
            }, 0);
        });
    }

    static template = "custom_org_chart_extension.JobOrgChart";
}

registry.category("actions").add("custom_org_chart_extension.job_chart", JobOrgChart);
