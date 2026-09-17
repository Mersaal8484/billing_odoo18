/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ReadingRejectionDialog } from "./components/rejection_dialog";
import { ReadingImageLightbox } from "./components/image_lightbox";

export class ReadingReviewWorkspaceAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            items: [],
            isReplacementTab: false,
            pagination: { page: 1, page_size: 40, total: 0, pages: 1, offset: 0 },
            stats: { pending: 0, approved: 0, rejected: 0, exceptions: 0 },
            filters: {
                period_id: "",
                region_id: "",
                batch_id: "",
                status: "under_review",
                anomaly_filter: "all",
                review_tab: "commercial",
                search: "",
                page_size: 40,
            },
            masterData: {
                periods: [],
                regions: [],
                batches: [],
            },
            activeLightboxReading: null,
            activeLightboxIndex: -1,
            activeRejectionReading: null,
            fastReviewMode: false,
            selectedIds: [],
        });

        this.debounceSearchTimeout = null;

        onWillStart(async () => {
            this.applyActionContext();
            await Promise.all([this.loadMasterData(), this.loadQueue(0, true)]);
        });

        onMounted(() => {});
    }

    applyActionContext() {
        const ctx = this.props.action && this.props.action.context;
        if (ctx) {
            if (ctx.default_batch_id) this.state.filters.batch_id = String(ctx.default_batch_id);
            if (ctx.default_period_id) this.state.filters.period_id = String(ctx.default_period_id);
            if (ctx.default_region_id) this.state.filters.region_id = String(ctx.default_region_id);
        }
    }

    async loadMasterData() {
        try {
            const [periods, regions, batches] = await Promise.all([
                this.orm.searchRead("date.range", [["work_type", "=", "readings"]], ["id", "name"], { limit: 50, order: "date_start desc" }),
                this.orm.searchRead("utility.region", [["type", "=", "region"]], ["id", "name"], { limit: 100, order: "name asc" }),
                this.orm.searchRead("utility.reading.batch", [["state", "!=", "draft"]], ["id", "name"], { limit: 100, order: "id desc" }),
            ]);

            this.state.masterData.periods = periods;
            this.state.masterData.regions = regions;
            this.state.masterData.batches = batches;
        } catch (e) {
            console.error("Failed to load master data for Reading Review Workspace:", e);
        }
    }

    async loadQueue(offset = 0, includeStats = false) {
        this.state.loading = true;
        try {
            const res = await this.orm.call("utility.reading.review.service", "get_review_queue", [], {
                period_id: this.state.filters.period_id ? parseInt(this.state.filters.period_id) : false,
                region_id: this.state.filters.region_id ? parseInt(this.state.filters.region_id) : false,
                batch_id: this.state.filters.batch_id ? parseInt(this.state.filters.batch_id) : false,
                status: this.state.filters.status,
                anomaly_filter: this.state.filters.anomaly_filter,
                review_tab: this.state.filters.review_tab,
                search: this.state.filters.search,
                offset: offset,
                limit: parseInt(this.state.filters.page_size) || 40,
                include_stats: includeStats,
            });

            this.state.items = res.items;
            this.state.isReplacementTab = !!res.is_replacement_tab;
            this.state.pagination = res.pagination;
            if (includeStats && res.stats) {
                this.state.stats = res.stats;
            }
            this.state.selectedIds = [];
            if (!this.state.items.length) {
                this.state.activeLightboxIndex = -1;
                this.state.activeLightboxReading = null;
            }
        } catch (e) {
            this.notification.add(_t("خطأ أثناء جلب قائمة مراجعة القراءات: ") + (e.message || e), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onSelectTab(tabName) {
        this.state.filters.review_tab = tabName;
        this.loadQueue(0, true);
    }

    async onApproveReplacementPair(replItem) {
        try {
            const res = await this.orm.call("utility.reading.review.service", "action_approve_replacement_pair", [], {
                replacement_id: replItem.id,
            });

            if (res.status === "success") {
                this.notification.add(_t("تم اعتماد عملية استبدال العداد بنجاح: ") + replItem.name, { type: "success" });
                replItem.state = "done";
            } else {
                this.notification.add(res.message || _t("تعذر اعتماد الاستبدال"), { type: "warning" });
            }
        } catch (e) {
            this.notification.add(e.message || _t("خطأ أثناء اعتماد عملية الاستبدال"), { type: "danger" });
        }
    }

    onFilterChange() {
        this.loadQueue(0, true);
    }

    onFilterByStatus(status) {
        this.state.filters.status = status;
        this.loadQueue(0, true);
    }

    onSearchInput(ev) {
        this.state.filters.search = ev.target.value;
        if (this.debounceSearchTimeout) {
            clearTimeout(this.debounceSearchTimeout);
        }
        this.debounceSearchTimeout = setTimeout(() => {
            this.loadQueue(0, true);
        }, 300);
    }

    async onApproveRow(reading) {
        try {
            const res = await this.orm.call("utility.reading.review.service", "action_approve_review", [], {
                reading_ids: [reading.id],
            });

            if (res.status === "success") {
                this.notification.add(_t("تم اعتماد قراءة العداد بنجاح: ") + reading.meter_number, { type: "success" });
                
                // Optimistic local update
                reading.state = "approved";
                this.state.stats.approved += 1;
                if (this.state.stats.pending > 0) this.state.stats.pending -= 1;

                // Close lightbox if open
                if (this.state.activeLightboxReading && this.state.activeLightboxReading.id === reading.id) {
                    this.onCloseLightbox();
                }
            } else {
                this.notification.add(res.message || _t("تعذر الاعتماد"), { type: "warning" });
            }
        } catch (e) {
            this.notification.add(e.message || _t("خطأ أثناء الاعتماد"), { type: "danger" });
        }
    }

    onRejectRow(reading) {
        this.state.activeRejectionReading = reading;
        if (this.state.activeLightboxReading && this.state.activeLightboxReading.id === reading.id) {
            this.onCloseLightbox();
        }
    }

    async onConfirmRejection(data) {
        const reading = this.state.activeRejectionReading;
        if (!reading) return;

        try {
            const res = await this.orm.call("utility.reading.review.service", "action_reject_review", [], {
                reading_ids: [reading.id],
                rejection_reason: data.reason,
                review_notes: data.notes,
            });

            if (res.status === "success") {
                this.notification.add(_t("تم رفض قراءة العداد: ") + reading.meter_number, { type: "warning" });
                
                reading.state = "draft";
                reading.rejection_reason = data.reason;
                this.state.stats.rejected += 1;
                if (this.state.stats.pending > 0) this.state.stats.pending -= 1;

                this.state.activeRejectionReading = null;

                if (this.state.activeLightboxReading && this.state.activeLightboxReading.id === reading.id) {
                    this.onCloseLightbox();
                }
            } else {
                this.notification.add(res.message || _t("تعذر الرفض"), { type: "danger" });
            }
        } catch (e) {
            this.notification.add(e.message || _t("خطأ أثناء الرفض"), { type: "danger" });
        }
    }

    onCloseRejectionDialog() {
        this.state.activeRejectionReading = null;
    }

    onOpenLightbox(reading) {
        this.state.activeLightboxReading = reading;
        this.state.activeLightboxIndex = this.state.items.findIndex(r => r.id === reading.id);
    }

    async onSetImageState(reading, imageState) {
        try {
            const res = await this.orm.call("utility.reading.review.service", "action_set_image_state", [], {
                reading_ids: [reading.id],
                image_state: imageState,
            });

            if (res.status === "success") {
                const labels = {
                    clear: _t("واضحة"),
                    not_clear: _t("غير واضحة"),
                    not_same: _t("غير مطابقة للعداد"),
                    loss_read: _t("قراءة ضائعة / تعذر القراءة"),
                    pending: _t("بانتظار المراجعة"),
                };
                this.notification.add(_t("تم تحديث حالة الصورة: ") + (labels[imageState] || imageState), { type: "success" });
                reading.image_state = imageState;
            } else {
                this.notification.add(res.message || _t("تعذر تحديث حالة الصورة"), { type: "warning" });
            }
            if (this.state.activeLightboxReading && this.state.activeLightboxReading.id === reading.id) {
                this.onCloseLightbox();
            }
        } catch (e) {
            this.notification.add(e.message || _t("خطأ أثناء تحديث حالة الصورة"), { type: "danger" });
        }
    }

    async onMarkImageClear(reading) {
        return this.onSetImageState(reading, "clear");
    }

    onCloseLightbox() {
        this.state.activeLightboxReading = null;
        this.state.activeLightboxIndex = -1;
    }

    onNextLightboxReading() {
        if (!this.state.activeLightboxReading) return;
        const idx = this.state.items.findIndex(r => r.id === this.state.activeLightboxReading.id);
        if (idx !== -1 && idx < this.state.items.length - 1) {
            this.state.activeLightboxReading = this.state.items[idx + 1];
            this.state.activeLightboxIndex = idx + 1;
        }
    }

    onPreviousLightboxReading() {
        if (!this.state.activeLightboxReading) return;
        const idx = this.state.items.findIndex(r => r.id === this.state.activeLightboxReading.id);
        if (idx > 0) {
            this.state.activeLightboxReading = this.state.items[idx - 1];
            this.state.activeLightboxIndex = idx - 1;
        }
    }

    toggleSelectAll(ev) {
        if (ev.target.checked) {
            this.state.selectedIds = this.state.items.map(r => r.id);
        } else {
            this.state.selectedIds = [];
        }
    }

    toggleSelectRow(readingId) {
        const idx = this.state.selectedIds.indexOf(readingId);
        if (idx === -1) {
            this.state.selectedIds.push(readingId);
        } else {
            this.state.selectedIds.splice(idx, 1);
        }
    }

    async onBulkApprove() {
        if (!this.state.selectedIds.length) return;
        try {
            const res = await this.orm.call("utility.reading.review.service", "action_bulk_approve_safe", [], {
                reading_ids: this.state.selectedIds,
            });

            if (res.status === "success") {
                this.notification.add(_t("تم الاعتماد الجملي بنجاح لـ ") + res.count + _t(" قراءة."), { type: "success" });
                await this.loadQueue(this.state.pagination.offset, true);
            } else {
                this.notification.add(res.message || _t("تعذر الاعتماد الجملي"), { type: "warning" });
            }
        } catch (e) {
            this.notification.add(e.message || _t("خطأ أثناء الاعتماد الجملي"), { type: "danger" });
        }
    }

    changePage(newPage) {
        if (newPage < 1 || newPage > this.state.pagination.pages) return;
        const newOffset = (newPage - 1) * this.state.pagination.page_size;
        this.loadQueue(newOffset, false);
    }
}

ReadingReviewWorkspaceAction.template = "utility_billing.ReadingReviewWorkspaceAction";
ReadingReviewWorkspaceAction.components = {
    ReadingRejectionDialog,
    ReadingImageLightbox,
};

registry.category("actions").add("utility_reading_review_workspace", ReadingReviewWorkspaceAction);
