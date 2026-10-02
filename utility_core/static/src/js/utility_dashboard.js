/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState, onMounted, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

class UtilityDashboard extends Component {
    static props = { ...standardActionServiceProps };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            selectedRegionId: false,
            regions: [],
            isDataLoaded: false,
            isLoading: false,
            kpi: {
                today_postpaid: 0,
                today_billed: 0,
                total_debt: 0,
                overdue_debt: 0,
                overdue_count: 0,
                active_customers: 0,
                chart_labels: [],
                chart_invoices: [],
                chart_collections: [],
                region_rows: [],
                region_chart_labels: [],
                region_chart_customers: [],
                region_chart_debt: [],
            },
        });
        this.chartCanvasRef = useRef("chartCanvas");
        this.regionChartCanvasRef = useRef("regionChartCanvas");
        this.chart = null;
        this.regionChart = null;
        this.renderTimeout = null;

        onWillStart(async () => {
            const regions = await this.orm.searchRead("utility.region", [["type", "=", "region"]], ["id", "name"], { order: "name" });
            this.state.regions = regions;
            await loadJS("/web/static/lib/Chart/Chart.js");
            // Data is NOT fetched on page load per user instructions
        });

        onMounted(() => {
            if (this.state.isDataLoaded && this.state.kpi.chart_labels.length) {
                this.renderChart();
                this.renderRegionChart();
            }
        });

        onWillUnmount(() => {
            if (this.renderTimeout) {
                clearTimeout(this.renderTimeout);
                this.renderTimeout = null;
            }
            this.destroyCharts();
        });
    }

    async loadKPI(regionId) {
        this.state.isLoading = true;
        try {
            const res = await rpc("/utility/dashboard/kpi", { region_id: regionId || false });
            if (res) {
                this.state.kpi = res;
                this.state.isDataLoaded = true;
            }
            this.destroyCharts();
            if (this.renderTimeout) {
                clearTimeout(this.renderTimeout);
            }
            this.renderTimeout = setTimeout(() => {
                this.renderTimeout = null;
                this.renderChart();
                this.renderRegionChart();
            }, 100);
        } finally {
            this.state.isLoading = false;
        }
    }

    onRegionChange(ev) {
        this.state.selectedRegionId = ev.target.value ? parseInt(ev.target.value) : false;
    }

    async onFetchClick() {
        await this.loadKPI(this.state.selectedRegionId);
    }

    formatMoney(val) {
        return new Intl.NumberFormat('ar-YE', { maximumFractionDigits: 2 }).format(val || 0);
    }

    destroyCharts() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        if (this.regionChart) {
            this.regionChart.destroy();
            this.regionChart = null;
        }
    }

    renderChart() {
        if (!this.chartCanvasRef.el) return;
        const ctx = this.chartCanvasRef.el.getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.kpi.chart_labels || [],
                datasets: [
                    {
                        label: 'الفواتير الآجلة الصادرة (ريال)',
                        data: this.state.kpi.chart_invoices || [],
                        backgroundColor: '#3b82f6',
                        borderColor: '#2563eb',
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'تحصيلات الدفع الآجل (ريال)',
                        data: this.state.kpi.chart_collections || [],
                        backgroundColor: '#10b981',
                        borderColor: '#059669',
                        borderWidth: 1,
                        borderRadius: 4,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        rtl: true,
                        labels: {
                            font: { family: 'Cairo, Segoe UI, sans-serif', size: 12 },
                        },
                    },
                    tooltip: {
                        rtl: true,
                        callbacks: {
                            label: (context) => {
                                const datasetLabel = context.dataset.label || '';
                                return `${datasetLabel}: ${this.formatMoney(context.parsed.y)} ريال`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            font: { family: 'Cairo, Segoe UI, sans-serif' },
                        },
                    },
                    y: {
                        beginAtZero: true,
                        position: 'right',
                    },
                }
            }
        });
    }

    renderRegionChart() {
        if (!this.regionChartCanvasRef.el) return;
        const ctx = this.regionChartCanvasRef.el.getContext('2d');
        this.regionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.kpi.region_chart_labels || [],
                datasets: [
                    {
                        label: 'مشتركو الدفع الآجل',
                        data: this.state.kpi.region_chart_customers || [],
                        backgroundColor: '#6366f1',
                    },
                    {
                        label: 'إجمالي المديونية الآجلة (ريال)',
                        data: this.state.kpi.region_chart_debt || [],
                        backgroundColor: '#ef4444',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        rtl: true,
                        labels: {
                            font: { family: 'Cairo, Segoe UI, sans-serif', size: 12 },
                        },
                    },
                    tooltip: {
                        rtl: true,
                        callbacks: {
                            label: (context) => {
                                const datasetLabel = context.dataset.label || '';
                                return `${datasetLabel}: ${this.formatMoney(context.parsed.y)}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            font: { family: 'Cairo, Segoe UI, sans-serif' },
                        },
                    },
                    y: {
                        beginAtZero: true,
                        position: 'right',
                    },
                },
            },
        });
    }

    openCustomers(regionId = null) {
        const rid = (typeof regionId === 'number') ? regionId : false;
        const domain = [['state', '=', 'active']];
        if (rid) {
            domain.push(['region_id', '=', rid]);
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: rid ? 'مشتركو المنطقة (دفع آجل)' : 'إجمالي مشتركي الدفع الآجل',
            res_model: 'utility.customer',
            views: [[false, 'list'], [false, 'form']],
            view_mode: 'list,form',
            domain: domain,
            context: {'group_by': 'region_id'},
        });
    }

    openPostpaidOrders(regionId = null) {
        const rid = (typeof regionId === 'number') ? regionId : false;
        const domain = [['bill_state', 'in', ['confirmed', 'sent', 'overdue']], ['balance_due', '>', 0]];
        if (rid) {
            const row = (this.state.kpi.region_rows || []).find((item) => item.region_id === rid);
            const partnerIds = (row && Array.isArray(row.partner_ids)) ? row.partner_ids : [];
            domain.push(['partner_id', 'in', partnerIds]);
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'فواتير الدفع الآجل القائمة',
            res_model: 'sale.order',
            views: [[false, 'list'], [false, 'form']],
            view_mode: 'list,form',
            domain: domain,
        });
    }

    openOverdueOrders(regionId = null) {
        const rid = (typeof regionId === 'number') ? regionId : false;
        const domain = [['bill_state', '=', 'overdue']];
        if (rid) {
            const row = (this.state.kpi.region_rows || []).find((item) => item.region_id === rid);
            const partnerIds = (row && Array.isArray(row.partner_ids)) ? row.partner_ids : [];
            domain.push(['partner_id', 'in', partnerIds]);
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'فواتير الدفع الآجل المتأخرة',
            res_model: 'sale.order',
            views: [[false, 'list'], [false, 'form']],
            view_mode: 'list,form',
            domain: domain,
        });
    }

    openTodayPayments(regionId = null) {
        const rid = (typeof regionId === 'number') ? regionId : false;
        const domain = [['state', '=', 'posted'], ['payment_type', '=', 'inbound']];
        if (rid) {
            const row = (this.state.kpi.region_rows || []).find((item) => item.region_id === rid);
            const partnerIds = (row && Array.isArray(row.partner_ids)) ? row.partner_ids : [];
            domain.push(['partner_id', 'in', partnerIds]);
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'تحصيلات اليوم (دفع آجل)',
            res_model: 'account.payment',
            views: [[false, 'list'], [false, 'form']],
            view_mode: 'list,form',
            domain: domain,
        });
    }
}

UtilityDashboard.template = "utility_dashboard.UtilityDashboard";
registry.category("actions").add("utility_dashboard_action", UtilityDashboard);
