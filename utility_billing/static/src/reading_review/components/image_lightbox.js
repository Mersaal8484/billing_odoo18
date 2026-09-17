/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";

export class ReadingImageLightbox extends Component {
    setup() {
        this.modalRef = useRef("modalRoot");
        this.state = useState({
            zoom: 1.0,
            rotation: 0,
            variant: "review",
            markingClear: false,
        });

        this.handleKeyDown = this.handleKeyDown.bind(this);
        this.onBackdropClick = this.onBackdropClick.bind(this);
        this.onApprove = this.onApprove.bind(this);
        this.onReject = this.onReject.bind(this);
        this._prefetched = new Set();

        onMounted(() => {
            window.addEventListener("keydown", this.handleKeyDown, true);
            this.modalRef.el?.focus();
            this.prefetchNeighborImages(this.props);
        });

        onWillUnmount(() => {
            window.removeEventListener("keydown", this.handleKeyDown, true);
        });

        onWillUpdateProps((nextProps) => {
            this.prefetchNeighborImages(nextProps);
        });
    }

    handleKeyDown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClose();
            return;
        }

        if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA" || ev.target.tagName === "SELECT") {
            return;
        }

        if (ev.key === "ArrowLeft") {
            this.props.onNext();
        } else if (ev.key === "ArrowRight") {
            this.props.onPrevious();
        } else if (ev.key === "+") {
            this.zoomIn();
        } else if (ev.key === "-") {
            this.zoomOut();
        } else if (ev.key === "a" || ev.key === "A") {
            this.onApprove();
        } else if (ev.key === "r" || ev.key === "R") {
            this.onReject();
        } else if (ev.key === "c" || ev.key === "C") {
            if (this.isImageClear()) return;
            this.onMarkImageClear();
        }
    }

    onBackdropClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.props.onClose();
        }
    }

    onApprove() {
        this.props.onClose();
        this.props.onApprove(this.props.reading);
    }

    onReject() {
        this.props.onClose();
        this.props.onReject(this.props.reading);
    }

    zoomIn() {
        this.state.zoom = Math.min(this.state.zoom + 0.25, 3.5);
    }

    zoomOut() {
        this.state.zoom = Math.max(this.state.zoom - 0.25, 0.5);
    }

    rotateLeft() {
        this.state.rotation = (this.state.rotation - 90) % 360;
    }

    rotateRight() {
        this.state.rotation = (this.state.rotation + 90) % 360;
    }

    resetTransform() {
        this.state.zoom = 1.0;
        this.state.rotation = 0;
    }

    setVariant(varName) {
        this.state.variant = varName;
        this.resetTransform();
    }

    _prefetchUrl(url) {
        if (!url || this._prefetched.has(url)) {
            return;
        }
        this._prefetched.add(url);
        const img = new Image();
        img.src = url;
    }

    prefetchNeighborImages(props) {
        const items = props.items || [];
        if (!items.length || !props.reading) {
            return;
        }

        let idx = Number.isInteger(props.currentIndex) ? props.currentIndex : items.findIndex((item) => item.id === props.reading.id);
        if (idx < 0) {
            idx = items.findIndex((item) => item.id === props.reading.id);
        }

        const candidateIndexes = [idx, idx - 1, idx + 1, idx - 2, idx + 2];
        for (const candidate of candidateIndexes) {
            if (candidate < 0 || candidate >= items.length) {
                continue;
            }
            const reading = items[candidate];
            if (!reading || !reading.review_url) {
                continue;
            }
            this._prefetchUrl(reading.review_url);
        }
    }

    getImageUrl() {
        const r = this.props.reading;
        if (!r) return '';
        if (this.state.variant === 'original') {
            return r.original_url || r.review_url || r.thumbnail_url || '';
        } else if (this.state.variant === 'thumbnail') {
            return r.thumbnail_url || r.review_url || '';
        }
        return r.review_url || r.thumbnail_url || '';
    }

    /**
     * Returns true if the current reading's image is already marked as clear.
     */
    isImageClear() {
        return this.props.reading && this.props.reading.image_state === 'clear';
    }

    /**
     * Calls action_mark_images_clear via the parent's handler,
     * then updates image_state locally for immediate UI feedback.
     */
    async onMarkImageClear() {
        return this.onSetImageState('clear');
    }

    async onSetImageState(imageState) {
        if (this.state.markingClear) return;
        this.state.markingClear = true;
        try {
            if (this.props.onSetImageState) {
                await this.props.onSetImageState(this.props.reading, imageState);
            } else if (this.props.onMarkImageClear && imageState === 'clear') {
                await this.props.onMarkImageClear(this.props.reading);
            }
        } finally {
            this.state.markingClear = false;
            this.props.onClose();
        }
    }
}

ReadingImageLightbox.template = "utility_billing.ReadingImageLightbox";
ReadingImageLightbox.props = {
    reading: Object,
    items: { type: Array, optional: true },
    currentIndex: { type: Number, optional: true },
    onClose: Function,
    onNext: Function,
    onPrevious: Function,
    onApprove: Function,
    onReject: Function,
    onMarkImageClear: { type: Function, optional: true },
    onSetImageState: { type: Function, optional: true },
};
