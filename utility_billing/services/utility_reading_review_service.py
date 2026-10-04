import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class UtilityReadingReviewService(models.AbstractModel):
    _name = 'utility.reading.review.service'
    _description = 'مخدم مراجعة وتدقيق قراءات العدادات الرقمية'

    def _build_geographic_domain(self, user):
        """Build geographic scope domain — Admin only is unrestricted.

        مصدر الحقيقة: user.assigned_region_ids (موحد لكل الأدوار).
        Default-Deny: بدون مناطق → لا قراءات.
        الشبكي: account_id = False → تحح عبر meter_id.region_id.
        """
        if user.has_group('utility_core.group_utility_admin'):
            return []
        regions = user.assigned_region_ids
        if not regions:
            return [('id', '=', False)]
        return [
            '|',
            ('account_id.region_id', 'in', regions.ids),
            '&',
            ('account_id', '=', False),
            ('meter_id.region_id', 'in', regions.ids),
        ]

    def _build_review_scope_domain(self, period_id=False, region_id=False, batch_id=False, review_tab='commercial'):
        """Build the reusable scope domain for queue queries."""
        domain = []
        if period_id:
            domain.append(('date_range_id', '=', int(period_id)))
        if batch_id:
            domain.append(('image_asset_id.batch_id', '=', int(batch_id)))

        if review_tab == 'commercial':
            domain.append(('is_billable', '=', True))
        elif review_tab == 'network':
            domain.append(('reading_category', 'in', ['transformer', 'feeder']))
            domain.append(('is_private_transformer', '=', False))
        elif review_tab == 'exceptions':
            # Opening readings are initialization data, not review exceptions.
            # Their image state may legitimately be ``none`` because no field
            # photo is required for an opening event.
            domain.append(('reading_purpose', '!=', 'opening'))
            domain.append('|')
            domain.append(('consumption_alert', '!=', 'normal'))
            domain.append(('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read']))
        return domain

    def _build_reading_region_domain(self, region_id):
        """Build a geography domain for utility.reading that supports customer and network readings."""
        if not region_id:
            return []
        region_id = int(region_id)
        return [
            '|',
            ('account_id.region_id', '=', region_id),
            '&',
            ('account_id', '=', False),
            ('meter_id.region_id', '=', region_id),
        ]

    def _build_replacement_geographic_domain(self, user):
        """Build the user scope domain for replacement queues."""
        if user.has_group('utility_core.group_utility_admin'):
            return []
        regions = user.assigned_region_ids
        if not regions:
            return [('id', '=', False)]
        return [
            '|', '|',
            ('utility_account_id.region_id', 'in', regions.ids),
            ('feeder_id.region_id', 'in', regions.ids),
            ('transformer_id.region_id', 'in', regions.ids),
        ]

    def _build_replacement_region_domain(self, region_id):
        """Build the explicit region filter for replacement queues."""
        if not region_id:
            return []
        region_id = int(region_id)
        return [
            '|', '|',
            ('utility_account_id.region_id', '=', region_id),
            ('feeder_id.region_id', '=', region_id),
            ('transformer_id.region_id', '=', region_id),
        ]

    def _build_review_status_domain(self, status='under_review'):
        """Build the reusable status domain for queue queries."""
        if status == 'under_review':
            return [('state', '=', 'under_review')]
        if status == 'approved':
            return [('state', 'in', ['approved', 'queued', 'billed'])]
        if status == 'rejected':
            return [('state', '=', 'draft'), ('rejection_reason', '!=', False)]
        if status == 'exceptions':
            return ['|', ('state', '=', 'error'), ('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read'])]
        if status == 'all':
            return [('state', 'in', ['under_review', 'approved', 'queued', 'billed', 'draft', 'error'])]
        return [('state', '=', status)]

    def _build_review_anomaly_domain(self, anomaly_filter='all'):
        """Build anomaly filter domain separately to keep stats composition safe."""
        if anomaly_filter == 'high_consumption':
            return [('consumption_alert', '=', 'high')]
        if anomaly_filter == 'negative_consumption':
            return [('consumption_alert', '=', 'negative')]
        if anomaly_filter == 'zero_consumption':
            return [('consumption_alert', '=', 'zero')]
        if anomaly_filter == 'image_issues':
            return [('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read'])]
        if anomaly_filter == 'anomalies':
            return ['|', ('consumption_alert', '!=', 'normal'), ('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read'])]
        return []

    def _build_reading_review_domain(self, user, period_id=False, region_id=False, batch_id=False, status='under_review', anomaly_filter='all', review_tab='commercial', search=''):
        """Compose the final queue domain from orthogonal pieces."""
        domain = []
        geo_domain = self._build_geographic_domain(user)
        if geo_domain:
            domain = expression.AND([domain, geo_domain])
        domain = expression.AND([domain, self._build_review_scope_domain(period_id, region_id, batch_id, review_tab)])
        domain = expression.AND([domain, self._build_review_status_domain(status)])
        domain = expression.AND([domain, self._build_review_anomaly_domain(anomaly_filter)])
        if search and search.strip():
            term = search.strip()
            domain = expression.AND([domain, ['|', '|', ('meter_id.meter_number', 'ilike', term), ('account_id.display_name', 'ilike', term), ('account_id.customer_number', 'ilike', term)]])
        return domain

    def _compute_review_stats(self, domain):
        """Compute queue stats using grouped counts instead of four independent searches."""
        Reading = self.env['utility.reading'].sudo()

        def _count(extra_domain):
            grouped = Reading.read_group(expression.AND([domain, extra_domain]), ['__count'], ['state'], lazy=False)
            return sum(row['__count'] for row in grouped)

        pending_count = _count([('state', '=', 'under_review')])
        approved_count = _count([('state', 'in', ['approved', 'queued', 'billed'])])
        rejected_count = _count([('state', '=', 'draft'), ('rejection_reason', '!=', False)])
        exceptions_count = _count(['|', ('state', '=', 'error'), ('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read'])])
        return {
            'pending': pending_count,
            'approved': approved_count,
            'rejected': rejected_count,
            'exceptions': exceptions_count,
        }

    def _build_review_stats_domain(self, user, period_id=False, region_id=False, batch_id=False, anomaly_filter='all', review_tab='commercial', search=''):
        """Build the shared stats domain without the current status filter."""
        domain = []
        geo_domain = self._build_geographic_domain(user)
        if geo_domain:
            domain = expression.AND([domain, geo_domain])
        domain = expression.AND([domain, self._build_review_scope_domain(period_id, region_id, batch_id, review_tab)])
        domain = expression.AND([domain, self._build_review_anomaly_domain(anomaly_filter)])
        if search and search.strip():
            term = search.strip()
            domain = expression.AND([domain, ['|', '|', ('meter_id.meter_number', 'ilike', term), ('account_id.display_name', 'ilike', term), ('account_id.customer_number', 'ilike', term)]])
        return domain


    def _build_context_aware_vee_flags(self, reading):
        """Context-aware VEE flags that respect reading purpose and event semantics."""
        vee_flags = []
        purpose = reading.reading_purpose
        event = reading.reading_event

        # --- Image-based VEE (all contexts) ---
        if reading.image_state == 'not_clear':
            vee_flags.append({'code': 'IMAGE_UNREADABLE', 'label': _('صورة غير واضحة'), 'level': 'danger'})
        elif reading.image_state == 'not_same':
            vee_flags.append({'code': 'IMAGE_MISMATCH', 'label': _('صورة لا تطابق العداد'), 'level': 'danger'})
        elif reading.image_state == 'none':
            vee_flags.append({'code': 'MISSING_IMAGE', 'label': _('بدون صورة عداد'), 'level': 'warning'})

        # --- Opening readings: zero consumption is EXPECTED, never flag it ---
        if purpose == 'opening':
            return vee_flags

        # --- Replacement closing: validate against previous reading of SAME OLD METER ---
        if purpose == 'replacement_closing':
            if reading.consumption < 0:
                vee_flags.append({'code': 'NEGATIVE_CLOSING', 'label': _('استهلاك سلبي في إغلاق الاستبدال'), 'level': 'danger'})
            return vee_flags

        # --- Periodic & closing readings (commercial & private transformer) ---
        if purpose in ('periodic', 'closing'):
            if reading.consumption < 0:
                vee_flags.append({'code': 'NEGATIVE_CONSUMPTION', 'label': _('استهلاك سلبي'), 'level': 'danger'})
            elif reading.consumption == 0:
                vee_flags.append({'code': 'ZERO_CONSUMPTION', 'label': _('استهلاك صفر'), 'level': 'info'})
            elif reading.consumption_alert == 'high':
                vee_flags.append({'code': 'HIGH_CONSUMPTION', 'label': _('استهلاك مرتفع جدًا'), 'level': 'warning'})

        return vee_flags

    def _build_reading_item(self, reading):
        """Build a single reading DTO for the review queue."""
        asset = reading.image_asset_id
        attachment = reading.attachment_id or (asset.original_attachment_id if asset else False)

        if attachment:
            thumb_url = f"/web/image/{attachment.id}"
            review_url = f"/web/image/{attachment.id}"
            orig_url = f"/web/image/{attachment.id}"
        elif asset and asset.asset_uuid:
            thumb_url = f"/utility/media/{asset.asset_uuid}/original"
            review_url = f"/utility/media/{asset.asset_uuid}/original"
            orig_url = f"/utility/media/{asset.asset_uuid}/original"
        else:
            thumb_url = ''
            review_url = ''
            orig_url = ''

        purpose_labels = {
            'opening': 'افتتاحية',
            'periodic': 'دورية',
            'closing': 'ختامية',
            'replacement_closing': 'إغلاق استبدال',
        }
        event_labels = {
            'normal': 'عادية',
            'installation': 'تركيب',
            'replacement': 'استبدال',
            'disconnection': 'فصل',
            'removal': 'إزالة',
            'contract_closure': 'إنهاء عقد',
        }

        vee_flags = self._build_context_aware_vee_flags(reading)

        return {
            'id': reading.id,
            'meter_number': reading.meter_id.meter_number if reading.meter_id else '',
            'account_name': reading.account_id.display_name if reading.account_id else (reading.feeder_id.name if reading.feeder_id else (reading.transformer_id.name if reading.transformer_id else '')),
            'subscriber_code': reading.account_id.customer_number if reading.account_id else '',
            'region_name': reading.account_id.region_id.name if reading.account_id and reading.account_id.region_id else '',
            'previous_reading': reading.previous_reading or 0.0,
            'current_reading': reading.reading_value or 0.0,
            'consumption': reading.billing_consumption or reading.consumption or 0.0,
            'reading_date': fields.Datetime.to_string(reading.reading_date) if reading.reading_date else '',
            'reading_category': reading.reading_category,
            'reading_purpose': reading.reading_purpose,
            'reading_purpose_label': purpose_labels.get(reading.reading_purpose, reading.reading_purpose),
            'reading_event': reading.reading_event,
            'reading_event_label': event_labels.get(reading.reading_event, reading.reading_event),
            'is_billable': reading.is_billable,
            'is_private_transformer': reading.is_private_transformer if hasattr(reading, 'is_private_transformer') else False,
            'meter_multiplier': reading.meter_multiplier or 1.0,
            'reading_type': reading.reading_type or 'manual',
            'state': reading.state,
            'image_state': reading.image_state or 'none',
            'consumption_alert': reading.consumption_alert or 'normal',
            # Asset is optional for legacy readings that still use only an
            # attachment.  Keep the DTO valid for both storage paths.
            'asset_uuid': asset.asset_uuid if asset else False,
            'thumbnail_url': thumb_url,
            'review_url': review_url,
            'original_url': orig_url,
            'rejection_reason': reading.rejection_reason or '',
            'review_notes': reading.review_notes or '',
            'reviewer_id': reading.reviewer_id.id if reading.reviewer_id else False,
            'reviewer_name': reading.reviewer_id.name if reading.reviewer_id else '',
            'review_date': fields.Datetime.to_string(reading.review_date) if reading.review_date else '',
            'has_anomaly': bool(reading.consumption_alert != 'normal' or reading.image_state in ['not_clear', 'not_same', 'none', 'loss_read']),
            'vee_flags': vee_flags,
        }

    @api.model
    def get_review_queue(self, period_id=False, region_id=False, batch_id=False, status='under_review', anomaly_filter='all', review_tab='commercial', search='', offset=0, limit=40, include_stats=True):
        """
        جلب قائمة مراجعة القراءات مقسمة حسب التبويب والطلب العملياتي (Commercial, Network, Replacements, Exceptions):
        - Commercial: القراءات التجارية القابلة للفوترة (المشتركين والمحولات الخاصة).
        - Network: قراءات الفيدرات والمحولات العامة ذات الطابع الفني والهندسي.
        - Replacements: عمليات استبدال العدادات المزدوجة (إغلاق القديم + افتتاح الجديد) بميزانية 20 عملية = 40 صورة مصغرة.
        - Exceptions: القراءات ذات التنبيهات الشديدة أو المشاكل الفنية بالصور.
        """
        user = self.env.user
        Reading = self.env['utility.reading'].sudo()
        limit_val = max(1, min(int(limit or 40), 40))
        stats_domain = self._build_review_stats_domain(
            user,
            period_id=period_id,
            region_id=region_id,
            batch_id=batch_id,
            anomaly_filter=anomaly_filter,
            review_tab=review_tab,
            search=search,
        )
        if region_id:
            stats_domain = expression.AND([stats_domain, self._build_reading_region_domain(region_id)])
        domain = expression.AND([stats_domain, self._build_review_status_domain(status)])
        if region_id:
            domain = expression.AND([domain, self._build_reading_region_domain(region_id)])

        # معالجة خاصة لتبويب الاستبدال (Meter Replacement Pair View)
        if review_tab == 'replacements':
            return self._get_replacements_queue(user, region_id, offset, include_stats=include_stats)

        # 7. جلب عدد السجلات الإجمالي والمجموعة الحالية المفهرسة
        total_count = Reading.search_count(domain)
        readings = Reading.search(domain, offset=offset, limit=limit_val, order='reading_date desc, id desc')

        items = [self._build_reading_item(r) for r in readings]

        pages_count = (total_count + limit_val - 1) // limit_val if total_count > 0 else 1
        current_page = (offset // limit_val) + 1 if limit_val > 0 else 1
        res = {
            'items': items,
            'pagination': {
                'page': current_page,
                'page_size': limit_val,
                'total': total_count,
                'pages': pages_count,
                'offset': offset,
            },
        }
        if include_stats:
            res['stats'] = self._compute_review_stats(stats_domain)
        else:
            res['stats'] = {}
        return res

    def _get_replacements_queue(self, user, region_id=False, offset=0, include_stats=True):
        """Build replacement pair review queue with 20 operations/page."""
        Replacement = self.env['utility.meter.replacement'].sudo()
        repl_domain = expression.AND([
            self._build_replacement_geographic_domain(user),
            self._build_replacement_region_domain(region_id),
        ])

        total_repls = Replacement.search_count(repl_domain)
        replacements = Replacement.search(repl_domain, offset=offset, limit=20, order='replace_date desc, id desc')

        repl_items = []
        for r in replacements:
            closing = r.closing_reading_id
            opening = r.opening_reading_id

            closing_asset = closing.image_asset_id if closing else False
            opening_asset = opening.image_asset_id if opening else False

            repl_items.append({
                'id': r.id,
                'name': r.name,
                'target_type': r.target_type,
                'target_name': (
                    r.utility_account_id.display_name if r.utility_account_id
                    else r.feeder_id.display_name if r.feeder_id
                    else r.transformer_id.display_name if r.transformer_id
                    else ''
                ),
                'subscriber_code': r.utility_account_id.customer_number if r.utility_account_id else '',
                'replace_date': fields.Datetime.to_string(r.replace_date) if r.replace_date else '',
                'reason': r.reason or '',
                'state': r.state,
                'old_meter': {
                    'reading_id': closing.id if closing else False,
                    'meter_number': r.old_meter_number or (closing.meter_id.meter_number if closing else ''),
                    'closing_reading': r.old_closing_reading,
                    'previous_reading': r.old_last_invo_reading,
                    'uninvoiced_consumption': r.old_uninvoiced_consumption,
                    'image_state': closing.image_state if closing else 'none',
                    'thumbnail_url': f"/utility/media/{closing_asset.asset_uuid}/thumbnail" if closing_asset else '',
                    'review_url': f"/utility/media/{closing_asset.asset_uuid}/review" if closing_asset else '',
                },
                'new_meter': {
                    'reading_id': opening.id if opening else False,
                    'meter_number': r.new_meter_number or (opening.meter_id.meter_number if opening else ''),
                    'opening_reading': r.new_opening_reading,
                    'multiplier': r.new_meter_val or 1.0,
                    'image_state': opening.image_state if opening else 'none',
                    'thumbnail_url': f"/utility/media/{opening_asset.asset_uuid}/thumbnail" if opening_asset else '',
                    'review_url': f"/utility/media/{opening_asset.asset_uuid}/review" if opening_asset else '',
                }
            })

        pages_count = (total_repls + 19) // 20 if total_repls > 0 else 1
        current_page = (offset // 20) + 1 if total_repls > 0 else 1

        res = {
            'items': repl_items,
            'is_replacement_tab': True,
            'pagination': {
                'page': current_page,
                'page_size': 20,
                'total': total_repls,
                'pages': pages_count,
                'offset': offset,
            },
        }
        if include_stats:
            stats_domain = self._build_geographic_domain(user)
            if region_id:
                stats_domain = expression.AND([stats_domain, self._build_replacement_region_domain(region_id)])
            res['stats'] = self._compute_review_stats(stats_domain)
        else:
            res['stats'] = {}
        return res

    def _check_geographic_access(self, readings, user):
        """Validate user has geographic scope for given readings.

        Admin فقط unrestricted. كل الأدوار الأخرى (بما فيها Auditor)
        تخضع لمنطق assigned_region_ids.
        يشمل القراءات الشبكية (بدون account) عبر meter_id.region_id.
        """
        if user.has_group('utility_core.group_utility_admin'):
            return
        regions = user.assigned_region_ids
        if not regions:
            raise AccessError(_("ليس لديك مناطق جغرافية محددة. يرجى التواصل مع المسؤول."))

        def _reading_region(r):
            if r.account_id and r.account_id.region_id:
                return r.account_id.region_id
            if r.meter_id and r.meter_id.region_id:
                return r.meter_id.region_id
            return False

        unauthorized = readings.filtered(
            lambda r: not _reading_region(r) or _reading_region(r) not in regions
        )
        if unauthorized:
            region_names = set()
            for r in unauthorized:
                reg = _reading_region(r)
                if reg:
                    region_names.add(reg.name)
            raise AccessError(
                _("ليس لديك صلاحية مراجعة قراءات المنطقة: %s")
                % ", ".join(sorted(region_names))
            )

    def _check_review_authority(self, user):
        """Keep image-review authority aligned with reading approval authority."""
        if not (
            user.has_group('utility_core.group_utility_supervisor')
            or user.has_group('utility_core.group_utility_billing_manager')
            or user.has_group('utility_core.group_utility_revenue_manager')
            or user.has_group('utility_core.group_utility_admin')
            or self.env.su
        ):
            raise AccessError(_(
                'ليس لديك صلاحية اعتماد حالة صورة العداد. '
                'يتطلب ذلك صلاحية مشرف أو مدير فوترة أو مدير إيرادات.'
            ))


    @api.model
    def action_mark_images_clear(self, reading_ids):
        """Record the review decision that the supplied meter evidence is clear.

        A reading remains under review after this action.  The separate
        ``action_approve_review`` transition is deliberately retained so a
        reviewer cannot accidentally approve a commercial reading merely by
        inspecting its image.
        """
        if not reading_ids:
            return {
                'status': 'error',
                'code': 'NO_READINGS_SELECTED',
                'message': _('لم يتم تحديد أي قراءة لاعتماد صورة العداد.'),
            }

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            return {
                'status': 'error',
                'code': 'READINGS_NOT_FOUND',
                'message': _('القراءات المحددة غير موجودة.'),
            }

        user = self.env.user
        self._check_review_authority(user)
        self._check_geographic_access(readings, user)

        eligible = readings.filtered(lambda reading: reading.state == 'under_review')
        if not eligible:
            return {
                'status': 'error',
                'code': 'IMAGE_REVIEW_STATE_INVALID',
                'message': _('يمكن اعتماد حالة الصورة للقراءات قيد المراجعة فقط.'),
            }

        without_image = eligible.filtered(
            lambda reading: not reading.image_asset_id and not reading.attachment_id
        )
        if without_image:
            return {
                'status': 'error',
                'code': 'IMAGE_EVIDENCE_MISSING',
                'message': _('لا يمكن اعتماد الصورة كواضحة لأن ملف صورة العداد غير موجود.'),
            }

        eligible.write({'image_state': 'clear'})
        _logger.info(
            'Meter image evidence marked clear for readings %s by user %s.',
            eligible.ids,
            user.id,
        )
        return {
            'status': 'success',
            'marked_ids': eligible.ids,
            'count': len(eligible),
        }

    @api.model
    def action_approve_review(self, reading_ids):
        """اعتماد قراءة أو مجموعة قراءات عبر النموذج الموحد action_approve()"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد أي قراءة للإعتماد.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            raise ValidationError(_("القراءات المحددة غير موجودة."))

        user = self.env.user
        self._check_geographic_access(readings, user)

        valid_readings = readings.filtered(lambda r: r.state in ['under_review', 'draft'])
        if not valid_readings:
            return {'status': 'error', 'message': _('القراءات المحددة تم اعتمادها أو فوترتها سابقاً.')}

        images_pending_review = valid_readings.filtered(
            lambda reading: reading._requires_billing_review()
            and reading.image_state != 'clear'
        )
        if images_pending_review:
            return {
                'status': 'error',
                'code': 'IMAGE_REVIEW_REQUIRED',
                'message': _(
                    'اعتمد صورة العداد كـ«واضحة» أولاً، ثم اعتمد القراءة.'
                ),
            }

        # Delegate to the authoritative model method (single source of truth)
        valid_readings.action_approve()

        return {
            'status': 'success',
            'approved_ids': valid_readings.ids,
            'count': len(valid_readings)
        }

    @api.model
    def action_reject_review(self, reading_ids, rejection_reason=None, review_notes=''):
        """رفض قراءة أو مجموعة قراءات عبر النموذج الموحد action_reject()"""
        if rejection_reason is None:
            rejection_reason = _('مرفوضة من قبل المراجع')

        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد أي قراءة للرفض.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            raise ValidationError(_("القراءات المحددة غير موجودة."))

        user = self.env.user
        self._check_geographic_access(readings, user)

        billed_readings = readings.filtered(lambda r: r.state == 'billed')
        if billed_readings:
            raise ValidationError(
                _("لا يمكن رفض قراءات مفوترة مباشرة (%s). يُرجى إلغاء الفاتورة أولاً.")
                % ", ".join(billed_readings.mapped('reading_id'))
            )

        # Write rejection metadata then delegate to model action_reject()
        readings.with_context(_bypass_reading_protection=True).write({
            'rejection_reason': rejection_reason,
            'review_notes': review_notes or False,
        })
        readings.action_reject()

        return {
            'status': 'success',
            'rejected_ids': readings.ids,
            'count': len(readings)
        }

    @api.model
    def action_bulk_approve_safe(self, reading_ids):
        """الاعتماد الجملي الآمن للقراءات المؤهلة خالياً من الشذوذ الحرج"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد قراءات للاعتماد الجملي.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids), ('state', '=', 'under_review')])

        eligible = readings.filtered(
            lambda r: r.image_state not in ['not_clear', 'not_same', 'none', 'loss_read']
            and r.consumption_alert != 'negative'
        )

        if not eligible:
            return {'status': 'error', 'message': _('لا توجد قراءات مراجعة سليمة مؤهلة للاعتماد الجملي بدون مراجعة ثانوية.')}

        return self.action_approve_review(eligible.ids)

    @api.model
    def action_approve_replacement_pair(self, replacement_id):
        """اعتماد عملية استبدال العداد المزدوجة (القراءة الختامية + القراءة الافتتاحية) دفعة واحدة.
        Approval means: closing → approved, opening → approved.
        The closing reading remains eligible for _get_unbilled_closing_components() until
        the next approved periodic reading creates the actual bill."""
        repl = self.env['utility.meter.replacement'].sudo().browse(replacement_id).exists()
        if not repl:
            raise ValidationError(_("عملية الاستبدال غير موجودة."))

        reading_ids = []
        if repl.closing_reading_id:
            reading_ids.append(repl.closing_reading_id.id)
        if repl.opening_reading_id:
            reading_ids.append(repl.opening_reading_id.id)

        if not reading_ids:
            return {'status': 'error', 'message': _('لا توجد قراءات مراجعة مسجلة لهذه العملية.')}

        res = self.action_approve_review(reading_ids)
        if res.get('status') == 'success':
            repl.write({'state': 'done'})
        return res

    @api.model
    def action_mark_images_clear(self, reading_ids):
        """اعتماد الصورة كصورة واضحة للقراءات المحددة"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد أي قراءة.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            raise ValidationError(_("القراءات المحددة غير موجودة."))

        user = self.env.user
        self._check_geographic_access(readings, user)

        readings.action_mark_image_clear()
        return {
            'status': 'success',
            'cleared_ids': readings.ids,
            'count': len(readings),
        }

    @api.model
    def action_set_image_state(self, reading_ids, image_state):
        """تحديث حالة الصورة لقراءة أو مجموعة قراءات"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد أي قراءة.')}

        if image_state not in ['none', 'pending', 'clear', 'not_clear', 'not_same', 'loss_read']:
            raise ValidationError(_('حالة الصورة المحددة غير صالحة.'))

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            raise ValidationError(_("القراءات المحددة غير موجودة."))

        user = self.env.user
        self._check_geographic_access(readings, user)
        readings._check_review_access()

        readings.with_context(_bypass_reading_protection=True).write({'image_state': image_state})
        return {
            'status': 'success',
            'updated_ids': readings.ids,
            'image_state': image_state,
            'count': len(readings),
        }
