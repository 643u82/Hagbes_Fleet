/** @odoo-module **/

import { Component, onWillStart, reactive, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class JobOrgChart extends Component {
    setup() {
        this.collapsedNodeSet = new Set();
        this.orm = useService("orm"); // ORM service for RPC calls
        this.action = useService("action");
        this.state = reactive({ nodes: [] });
        this.onEditClick = this.onEditClick.bind(this);
        this.chartContainerRef = useRef("chartContainer");
        this.zoomLevel = useState({ value: 1 });
        this.onWheelZoom = (ev) => {
            if (ev.ctrlKey || ev.metaKey) return; // Let browser zoom with Ctrl
            ev.preventDefault();
            const delta = ev.deltaY > 0 ? -0.1 : 0.1;
            this.zoomLevel.value = Math.max(0.1, Math.min(2.0, this.zoomLevel.value + delta));
            this.updateTransform();
        };
        this.currentX = 0;
        this.currentY = 0;


        onWillStart(async () => {
            const flatData = await this.orm.call(
                "hr.job",
                "get_org_chart_data",
                []
            );
            this.state.nodes = this.buildTree(flatData);
            this.state.loading = false;
        });

        onMounted(() => {
            const container = this.chartContainerRef.el;
            const chart = container.querySelector(".org-chart-root");

            let isDragging = false;
            let startX, startY;

            // Set initial cursor style
            container.style.cursor = "grab";

            container.addEventListener("mousedown", (e) => {
                isDragging = true;
                container.style.cursor = "grabbing";
                startX = e.clientX - this.currentX;   // use this.currentX
                startY = e.clientY - this.currentY;   // use this.currentY
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
                this.currentX = e.clientX - startX;  // update this.currentX
                this.currentY = e.clientY - startY;  // update this.currentY
                this.updateTransform();
            });
            container.addEventListener("wheel", this.onWheelZoom);

            setTimeout(() => {
                this.adjustChartPosition();
            }, 0);
        });
    }

     updateTransform() {
        const chart = this.chartContainerRef.el.querySelector(".org-chart-root");
        chart.style.transform = `
            translate(${this.currentX}px, ${this.currentY}px)
            scale(${this.zoomLevel.value})
        `;
    }

    // New method to keep chart horizontally centered and avoid shifting off-screen
    adjustChartPosition() {
    const container = this.chartContainerRef.el;
    const chart = container.querySelector(".org-chart-root");

    const containerWidth = container.clientWidth;
    const chartWidth = chart.clientWidth * this.zoomLevel.value;

    // Calculate horizontal offset: center chart or keep left boundary at 0
    const newX = Math.max((containerWidth - chartWidth) / 2, 0);
    const newY = 40;  // vertical offset, adjust if needed


    this.currentX = newX;
    this.currentY = newY;
    this.updateTransform();
}

adjustChartPositionSimple() {
    const container = this.chartContainerRef.el;
    const chart = container.querySelector(".org-chart-root");

    if (this.currentX < 0) {
        this.currentX = 0;
        this.updateTransform();
    }
}

    buildTree(flatData) {
    const idToNodeMap = {};
    const rootNodes = [];
    const orphanNodes = [];

    flatData.forEach((node) => {
        node.children = [];
        idToNodeMap[`${node.job_id}_${node.employee_id || 'vacant'}`] = node;
    });

    flatData.forEach((node) => {
        if (node.parent_job_id) {
            const parentCandidates = Object.values(idToNodeMap).filter(
                n => n.job_id === node.parent_job_id
            );
            if (parentCandidates.length > 0) {
                parentCandidates[0].children.push(node);
            } else {
                node.isRoot = true;
                rootNodes.push(node);
            }
        } else {
            node.isRoot = true;
            rootNodes.push(node);
        }
    });

    // Detect orphans: nodes with no parent and no children
    flatData.forEach((node) => {
        const hasParent = !!node.parent_job_id;
        const hasChildren = flatData.some(n => n.parent_job_id === node.job_id);
        if (!hasParent && !hasChildren) {
            orphanNodes.push(node);
        }
    });

    this.state.orphanNodes = orphanNodes;
    // Filter out orphans from main chart
    return rootNodes.filter(n => !orphanNodes.includes(n));
}



    onNodeClick(node) {
    if (node.employee_id) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee.public',
            res_id: node.employee_id,
            views: [[false, 'form']],
            target: 'current',
            flags: { readonly: true },
            context: {
                active_id: node.employee_id,
                form_view_initial_mode: 'view',
            },
        });
    }
}


    onEditClick(node) {
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'hr.job',
        res_id: node.job_id,
        views: [[false, 'form']],
        target: 'current',
        context: {
            warn_on_name_change: true,
        },
    });
}

    onImportJobs() {
    this.action.doAction({
        type: "ir.actions.client",
        tag: "import",
        params: {
            model: "hr.job",
        },
    });
}

    toggleCollapse = (node) => {
    const key = `${node.job_id}_${node.employee_id || 'vacant'}`;
    if (this.collapsedNodeSet.has(key)) {
        // Currently collapsed, so expand this node:
        this.collapsedNodeSet.delete(key);

        // Collapse all children nodes immediately so they don't auto-expand
        if (node.children && node.children.length) {
            for (const child of node.children) {
                const childKey = `${child.job_id}_${child.employee_id || 'vacant'}`;
                this.collapsedNodeSet.add(childKey);
            }
        }
    } else {
        // Currently expanded, so collapse this node
        this.collapsedNodeSet.add(key);
    }
    this.render();
    this.adjustChartPositionSimple();
  }


    onCreateJob() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.job',
            views: [[false, 'form']],
            target: 'current'
        });
    }
}

JobOrgChart.template = "custom_org_chart_extension.JobOrgChart";
registry.category("actions").add("custom_org_chart_extension.job_chart", JobOrgChart);
