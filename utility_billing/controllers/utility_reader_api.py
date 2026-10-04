import base64
import binascii
import json
import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class UtilityReaderAPI(http.Controller):
    """REST API لتطبيق القارئ (Flutter) — رفع القراءات والصور على شكل دفعات"""

    @staticmethod
    def _error(code, message):
        """Return the stable API error envelope without changing success payloads."""
        return {'success': False, 'code': code, 'error': message}

    @staticmethod
    def _http_json_response(payload, status=200):
        """Return a plain JSON response for non-JSON-RPC mobile uploads."""
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            content_type='application/json; charset=utf-8',
        )

    def _resolve_meter_identifiers(self, params):
        """Resolve supplied meter identifiers and reject contradictory values."""
        Meter = request.env['utility.meter'].sudo()
        identifiers = []
        if params.get('meter_id') not in (None, '', False):
            try:
                meter = Meter.search([('id', '=', int(params['meter_id']))], limit=1)
            except (TypeError, ValueError):
                meter = Meter.browse()
            identifiers.append(('meter_id', meter))
        for key in ('operational_number', 'meter_number'):
            value = params.get(key)
            if value not in (None, '', False):
                # Search using sudo() to ensure meter readers can lookup meters even if they don't have region-level access
                identifiers.append((key, Meter.search([(key, '=', str(value).strip())], limit=1)))
        if not identifiers:
            return Meter.browse(), 'IDENTIFIER_REQUIRED'
        if any(not meter for _, meter in identifiers):
            return Meter.browse(), 'METER_NOT_FOUND'
        meter_ids = {meter.id for _, meter in identifiers}
        if len(meter_ids) > 1:
            return Meter.browse(), 'METER_IDENTIFIER_MISMATCH'
        return identifiers[0][1], False

    @staticmethod
    def _check_meter_access_scope(meter):
        """Verify that the current user is authorized to lookup/query this meter."""
        user = request.env.user
        if not user:
            return False, ('UNAUTHORIZED', 'يرجى تسجيل الدخول أولاً.')

        # 1. Role verification (Functional Role)
        has_operational_role = (
            request.env.su
            or user.has_group('utility_core.group_utility_admin')
            or user.has_group('utility_core.group_utility_billing_manager')
            or user.has_group('utility_core.group_utility_supervisor')
            or user.has_group('utility_core.group_utility_meter_reader')
        )
        if not has_operational_role:
            return False, ('FORBIDDEN', 'لا تملك صلاحية الوصول إلى بيانات العداد.')

        # 2. Superuser / Admin has full system bypass
        if request.env.su or user.has_group('utility_core.group_utility_admin'):
            return True, None

        # Resolve scope independently from the functional role. A non-reader
        # with routes only must still be restricted to those routes.
        is_reader = user.has_group('utility_core.group_utility_meter_reader')
        assigned_routes = getattr(user, 'assigned_route_ids', False)
        is_global = getattr(user, '_is_global_utility_scope', lambda: False)()
        has_geographic_scope = bool(
            getattr(user, '_get_effective_branch_ids', lambda: [])()
            or getattr(user, '_get_effective_region_ids', lambda: [])()
        ) if not is_global else False
        if assigned_routes and (is_reader or (not is_global and not has_geographic_scope)):
            customer = meter.customer_id
            customer_route = customer.route_id if customer else False
            if not customer_route or customer_route not in assigned_routes:
                return False, (
                    'OUT_OF_SCOPE',
                    f'العداد {meter.meter_number} لا ينتمي إلى مسار مخصّص للمستخدم {user.name}.'
                )

        # 4. Geographic / Branch / Region scope check
        if is_global:
            return True, None

        if has_geographic_scope or not assigned_routes:
            if not hasattr(user, 'check_record_scope'):
                return False, ('OUT_OF_SCOPE', _('تعذر التحقق من النطاق التنظيمي للمستخدم.'))
            target = meter
            meter_region = getattr(meter, 'region_id', False) or (meter.customer_id and getattr(meter.customer_id, 'region_id', False))
            meter_area = getattr(meter, 'area_id', False) or (meter.customer_id and getattr(meter.customer_id, 'area_id', False))
            if not meter_region and not meter_area:
                route = getattr(meter, 'route_id', False) or (meter.customer_id and getattr(meter.customer_id, 'route_id', False))
                if route:
                    target = route
            try:
                user.check_record_scope(target)
            except AccessError as e:
                return False, ('OUT_OF_SCOPE', str(e))

        return True, None

    def _get_owned_batch(self, batch_id):
        try:
            batch_id = int(batch_id)
        except (TypeError, ValueError):
            return request.env['utility.reading.batch']
        return request.env['utility.reading.batch'].search([
            ('id', '=', batch_id),
            ('user_id', '=', request.env.uid),
        ], limit=1)
    # ================================================================
    # الخطوة 1: إنشاء سجل الدفعة
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/create', type='json',
                auth='user', methods=['POST'])
    def create_batch(self, **kwargs):
        """
        إنشاء دفعة رفع قراءات جديدة.
        يجب تمرير:
          - date_range_id: معرف الفترة (إلزامي)
          - region_id: معرف المنطقة (اختياري)
          - total_readings: عدد القراءات في الدفعة (اختياري — يُحسب من الـ JSON لاحقاً)
        """
        params = kwargs
        date_range_id = params.get('date_range_id')
        if not date_range_id:
            return self._error('VALIDATION_ERROR', 'date_range_id is required')

        # التحقق من صحة المعرف والفترة والشركة قبل إنشاء الدفعة
        try:
            date_range_id = int(date_range_id)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'date_range_id must be numeric')
        period = request.env['date.range'].browse(date_range_id)
        if (not period.exists() or period.period_role != 'reading'
                or period.state != 'open'
                or period.company_id not in (False, request.env.company)):
            return self._error('INVALID_READING_PERIOD', 'الفترة غير موجودة')

        region_id = params.get('region_id')
        if region_id:
            try:
                region_id = int(region_id)
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'region_id must be numeric')
        # The mobile client works from assigned routes and does not duplicate
        # the route region in local storage. When all assigned routes belong
        # to a single region, retain it on the batch for audit and validation.
        # A multi-region reader has a region-less batch and every line is
        # still validated against its assigned route while processing.
        if not region_id:
            route_region_ids = request.env.user.assigned_route_ids.mapped('region_id').ids
            if len(route_region_ids) == 1:
                region_id = route_region_ids[0]

        if region_id:
            region = request.env['utility.region'].browse(region_id)
            if (not region.exists() or region.type != 'region'
                    or (period.region_ids and region not in period.region_ids)):
                return self._error('INVALID_REGION', 'المنطقة غير صالحة لهذه الفترة')

        if (not request.env.user._is_global_utility_scope()
                and not request.env.user.assigned_route_ids
                and not request.env.user._get_effective_region_ids()):
            return self._error(
                'READER_SCOPE_NOT_ASSIGNED',
                'لا يوجد مسار أو نطاق جغرافي مخصّص للمستخدم الحالي.',
            )

        total_readings_raw = params.get('total_readings', 0)
        try:
            total_readings = int(total_readings_raw)
            if total_readings < 0:
                raise ValueError()
        except (TypeError, ValueError):
            return self._error(
                'INVALID_TOTAL_READINGS',
                'total_readings must be a non-negative integer',
            )

        batch = request.env['utility.reading.batch'].create({
            'date_range_id': date_range_id,
            'region_id': region_id or False,
            'total_readings': total_readings,
            # Set ownership explicitly so the record rule can safely allow
            # only the authenticated uploader's route-backed batch.
            'user_id': request.env.user.id,
        })
        return {
            'success': True,
            'batch_id': batch.id,
            'batch_name': batch.name,
        }

    # ================================================================
    # الخطوة 2: رفع ملف JSON (البيانات فقط — بدون صور)
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/upload_data', type='json',
                auth='user', methods=['POST'])
    def upload_batch_data(self, **kwargs):
        """
        رفع بيانات القراءات كملف JSON.
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
          - data: محتوى JSON كـ dict أو string (إلزامي)
        """
        params = kwargs
        batch_id = params.get('batch_id')
        data = params.get('data')
        if not batch_id or data is None:
            return self._error('VALIDATION_ERROR', 'batch_id and data are required')

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')
        if batch.state != 'uploaded':
            return self._error('BATCH_NOT_EDITABLE', 'لا يمكن تعديل دفعة تمت معالجتها')

        # تحويل البيانات وإثبات صحة الـ JSON قبل تنفيذ أي عملية كتابة
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                return self._error('INVALID_JSON', 'data must be valid JSON object')
            json_str = data
        elif isinstance(data, dict):
            parsed = data
            json_str = json.dumps(data, ensure_ascii=False)
        else:
            return self._error('INVALID_JSON', 'data must be dict or string')

        if not isinstance(parsed, dict):
            return self._error('INVALID_JSON', 'data must be valid JSON object')

        readings_list = parsed.get('readings')
        if readings_list is not None and not isinstance(readings_list, list):
            return self._error('INVALID_JSON', 'readings must be a list')

        encoded = base64.b64encode(json_str.encode('utf-8'))
        total = len(readings_list) if isinstance(readings_list, list) else 0

        batch.write({
            'data_file': encoded,
            'data_filename': f'{batch.name}.json',
            'total_readings': total or batch.total_readings,
        })

        return {
            'success': True,
            'batch_id': batch.id,
            'total_readings': batch.total_readings,
        }

    # ================================================================
    # الخطوة 3: رفع صورة واحدة (كمرفق مرتبط بالدفعة)
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/upload_image', type='json',
                auth='user', methods=['POST'])
    def upload_batch_image(self, **kwargs):
        """
        رفع صورة عداد واحدة كمرفق مرتبط بالدفعة.
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
          - filename: اسم الملف مثل MTR-001234_20260701.jpg (إلزامي)
          - image: محتوى الصورة بصيغة Base64 (إلزامي)
        """
        params = kwargs
        batch_id = params.get('batch_id')
        filename = params.get('filename')
        image_data = params.get('image')

        if not batch_id or not filename or not image_data:
            return self._error(
                'VALIDATION_ERROR',
                'batch_id, filename, and image are required',
            )

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')
        if batch.state != 'uploaded':
            return self._error('BATCH_NOT_EDITABLE', 'لا يمكن تعديل دفعة تمت معالجتها')

        # التحقق من حجم الصورة (الحد الأقصى 100 KB)
        max_size = int(request.env['ir.config_parameter'].sudo().get_param(
            'utility.max_image_size_kb', 100))
        try:
            decoded = base64.b64decode(image_data, validate=True)
            size_kb = len(decoded) / 1024
            if size_kb > max_size:
                return self._error(
                    'IMAGE_TOO_LARGE',
                    f'حجم الصورة ({size_kb:.0f} KB) يتجاوز الحد الأقصى ({max_size} KB)',
                )
        except (binascii.Error, TypeError, ValueError) as e:
            _logger.warning("Invalid base64 image data uploaded for batch %s: %s", batch_id, str(e))
            return self._error('INVALID_BASE64', 'بيانات الصورة غير صالحة (Base64 Decode Error)')

        media_asset = request.env['utility.media.service'].sudo().store_media(
            file_data=decoded,
            filename=filename,
            mimetype='image/jpeg',
            batch_id=batch.id,
            asset_type='meter_reading'
        )

        return {
            'success': True,
            'asset_uuid': media_asset.asset_uuid,
            'attachment_id': media_asset.original_attachment_id.id if media_asset.original_attachment_id else False,
            'filename': filename,
        }

    @http.route('/api/v1/utility/reading/batch/upload_image_multipart', type='http',
                auth='user', methods=['POST'], csrf=False)
    def upload_batch_image_multipart(self, **kwargs):
        """Upload one meter photo sent by the Flutter client as multipart data.

        The reading batch contains the image filename for every reading.  The
        batch processor uses that filename to attach the stored media asset to
        the matching reading when the batch is confirmed.
        """
        form = request.httprequest.form
        batch_id = form.get('batch_id') or kwargs.get('batch_id')
        uploaded_file = request.httprequest.files.get('file')
        filename = form.get('filename') or (
            uploaded_file.filename if uploaded_file else False
        )

        if not batch_id or not filename or not uploaded_file:
            return self._http_json_response(
                self._error(
                    'VALIDATION_ERROR',
                    'batch_id, filename, and file are required',
                ),
                status=400,
            )

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._http_json_response(
                self._error(
                    'BATCH_NOT_FOUND',
                    'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي',
                ),
                status=404,
            )
        if batch.state != 'uploaded':
            return self._http_json_response(
                self._error('BATCH_NOT_EDITABLE', 'لا يمكن تعديل دفعة تمت معالجتها'),
                status=409,
            )

        file_data = uploaded_file.read()
        if not file_data:
            return self._http_json_response(
                self._error('EMPTY_IMAGE', 'بيانات الصورة أو الملف فارغة.'),
                status=400,
            )

        max_size = int(request.env['ir.config_parameter'].sudo().get_param(
            'utility.max_image_size_kb', 100))
        size_kb = len(file_data) / 1024
        if size_kb > max_size:
            return self._http_json_response(
                self._error(
                    'IMAGE_TOO_LARGE',
                    f'حجم الصورة ({size_kb:.0f} KB) يتجاوز الحد الأقصى ({max_size} KB)',
                ),
                status=413,
            )

        media_asset = request.env['utility.media.service'].sudo().store_media(
            file_data=file_data,
            filename=filename,
            mimetype=uploaded_file.mimetype or 'image/jpeg',
            batch_id=batch.id,
            asset_type='meter_reading',
        )

        return self._http_json_response({
            'success': True,
            'asset_uuid': media_asset.asset_uuid,
            'attachment_id': (
                media_asset.original_attachment_id.id
                if media_asset.original_attachment_id else False
            ),
            'filename': filename,
            'reading_uuid': form.get('reading_uuid') or False,
        })

    # ================================================================
    # الخطوة 4: تأكيد اكتمال الرفع — بدء المعالجة
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/confirm', type='json',
                auth='user', methods=['POST'])
    def confirm_batch(self, **kwargs):
        """
        تأكيد اكتمال رفع الدفعة لبدء المعالجة بواسطة الـ Cron.
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
        """
        params = kwargs
        batch_id = params.get('batch_id')
        if not batch_id:
            return self._error('VALIDATION_ERROR', 'batch_id is required')

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')

        try:
            with request.env.cr.savepoint():
                batch.action_confirm()
            return {
                'success': True,
                'batch_id': batch.id,
                'batch_name': batch.name,
                'state': batch.state,
                'total_readings': batch.total_readings,
                'total_images': len(batch.image_ids),
            }
        except (AccessError, UserError, ValidationError) as e:
            _logger.warning("Failed to confirm reading batch %s: %s", batch_id, str(e))
            return self._error('BUSINESS_RULE_ERROR', str(e))

    # ================================================================
    # استعلام: حالة الدفعة (Polling)
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/status', type='json',
                auth='user', methods=['POST'])
    def batch_status(self, **kwargs):
        """
        استعلام عن حالة دفعة محددة (يستخدمه التطبيق للـ polling).
        يجب تمرير:
          - batch_id: معرف الدفعة (إلزامي)
        """
        params = kwargs
        batch_id = params.get('batch_id')
        if not batch_id:
            return self._error('VALIDATION_ERROR', 'batch_id is required')

        batch = self._get_owned_batch(batch_id)
        if not batch.exists():
            return self._error('BATCH_NOT_FOUND', 'الدفعة غير موجودة أو غير مملوكة للمستخدم الحالي')

        return {
            'success': True,
            'batch_id': batch.id,
            'batch_name': batch.name,
            'state': batch.state,
            'total_readings': batch.total_readings,
            'processed_count': batch.processed_count,
            'error_count': batch.error_count,
            'error_log': batch.error_log or '',
        }

    # ================================================================
    # استعلام: الفترات المتاحة
    # ================================================================
    @http.route('/api/v1/utility/reading/periods', type='json',
                auth='user', methods=['POST'])
    def get_periods(self, **kwargs):
        """
        جلب الفترات (الأشهر) المتاحة لربط القراءات بها.
        """
        user = request.env.user
        route_ids = user.assigned_route_ids.ids
        meter_reader = request.env['utility.meter.reader'].sudo().search(
            [('user_id', '=', user.id)], limit=1
        )
        if meter_reader:
            route_ids = list(set(route_ids + meter_reader.route_ids.ids))

        user_region_ids = request.env['utility.route'].sudo().browse(route_ids).mapped('region_id').ids

        domain = [
            ('period_role', '=', 'reading'),
            ('state', '=', 'open'),
            '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
        ]

        if user_region_ids:
            domain.extend(['|', ('region_ids', '=', False), ('region_ids', 'in', user_region_ids)])
        else:
            domain.append(('region_ids', '=', False))

        periods = request.env['date.range'].search(domain, order='date_start desc', limit=12)

        return {
            'success': True,
            'periods': [{
                'id': p.id,
                'name': p.name,
                'date_start': p.date_start.isoformat() if p.date_start else None,
                'date_end': p.date_end.isoformat() if p.date_end else None,
                'is_current': p.is_current_period,
            } for p in periods],
        }

    # ================================================================
    # استعلام: بحث عن عداد (للتطبيق)
    # ================================================================
    @http.route('/api/v1/utility/reading/meter/lookup', type='json',
                auth='user', methods=['POST'])
    def meter_lookup(self, **kwargs):
        """
        بحث عن عداد بالرقم — يستخدمه التطبيق للتحقق أثناء الإدخال.
        يجب تمرير:
          - meter_id أو operational_number أو meter_number: أحد معرفات العداد
        """
        params = dict(getattr(request, 'params', None) or getattr(request, 'jsonrequest', None) or {}, **kwargs)
        meter, error_code = self._resolve_meter_identifiers(params)
        if error_code == 'IDENTIFIER_REQUIRED':
            return self._error(
                'VALIDATION_ERROR',
                'meter_id, operational_number or meter_number is required',
            )
        if error_code == 'METER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'المعرفات الممررة للعداد متعارضة')
        if error_code:
            return self._error(error_code, 'العداد غير موجود')

        valid, error_info = self._check_meter_access_scope(meter)
        if not valid:
            code, msg = error_info
            return self._error(code, msg)

        customer = meter.customer_id

        # جلب آخر قراءة معتمدة أو مفوترة للعداد
        last_reading = request.env['utility.reading'].sudo().search([
            ('meter_id', '=', meter.id),
            ('state', 'in', ['approved', 'billed']),
        ], order='reading_date desc, id desc', limit=1)

        # Migrated accounts commonly carry their opening/last reading on the
        # meter and customer without a historical ``utility.reading`` record.
        # Do not turn that valid operational baseline into zero merely because
        # there is no canonical reading history yet.  When both sources exist,
        # use the most recent dated value.
        meter_baseline_value = meter.last_reading_value
        meter_baseline_date = meter.last_read_date
        if not meter_baseline_date and customer:
            meter_baseline_value = customer.last_reading_value
            meter_baseline_date = customer.last_reading_date

        use_historical_reading = bool(last_reading) and (
            not meter_baseline_date
            or not last_reading.reading_date
            or last_reading.reading_date >= meter_baseline_date
        )
        if use_historical_reading:
            last_reading_value = last_reading.reading_value
            last_reading_date = (
                last_reading.reading_date.isoformat()
                if last_reading.reading_date else None
            )
        else:
            last_reading_value = meter_baseline_value or 0.0
            last_reading_date = (
                meter_baseline_date.isoformat()
                if meter_baseline_date else None
            )

        # حساب متوسط الاستهلاك من آخر 6 قراءات معتمدة
        recent_readings = request.env['utility.reading'].sudo().search([
            ('meter_id', '=', meter.id),
            ('state', 'in', ['approved', 'billed']),
        ], order='reading_date desc, id desc', limit=6)

        avg_consumption = 0.0
        if len(recent_readings) >= 2:
            readings_list = sorted(recent_readings, key=lambda r: r.reading_date)
            consumptions = [
                max(0.0, readings_list[i].reading_value - readings_list[i - 1].reading_value)
                for i in range(1, len(readings_list))
            ]
            avg_consumption = sum(consumptions) / len(consumptions) if consumptions else 0.0

        return {
            'success': True,
            'meter': {
                'id': meter.id,
                'meter_number': meter.meter_number,
                'operational_number': meter.operational_number or None,
                'meter_type': meter.meter_type if hasattr(meter, 'meter_type') else None,
                'customer_id': customer.id if customer else None,
                'customer_name': customer.partner_id.name if customer and customer.partner_id else None,
                'customer_number': customer.customer_number if customer else None,
                'address': customer.address if customer and hasattr(customer, 'address') else None,
            },
            'last_reading_value': last_reading_value,
            'last_reading_date': last_reading_date,
            'avg_consumption': avg_consumption,
        }


    # ================================================================
    # استعلام: دفعات الجابي الحالي
    # ================================================================
    @http.route('/api/v1/utility/reading/batch/my', type='json',
                auth='user', methods=['POST'])
    def my_batches(self, **kwargs):
        """
        جلب دفعات الجابي الحالي (آخر 20 دفعة).
        """
        params = kwargs
        limit_raw = params.get('limit', 20)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return self._error('INVALID_LIMIT', 'limit must be an integer')

        limit = max(1, min(limit, 100))

        batches = request.env['utility.reading.batch'].search([
            ('user_id', '=', request.env.uid),
        ], order='upload_date desc', limit=limit)

        return {
            'success': True,
            'batches': [{
                'id': b.id,
                'name': b.name,
                'upload_date': b.upload_date.isoformat() if b.upload_date else None,
                'period': b.date_range_id.name if b.date_range_id else None,
                'total_readings': b.total_readings,
                'processed_count': b.processed_count,
                'error_count': b.error_count,
                'state': b.state,
            } for b in batches],
        }

    # ================================================================
    # استعلام: صلاحيات المستخدم (Mobile App Dashboard)
    # ================================================================
    @http.route('/api/v1/utility/auth/roles', type='json',
                auth='user', methods=['POST', 'GET'])
    def auth_roles(self, **kwargs):
        """
        يرجع أدوار المستخدم الحالي (كاشف، محصل، مشرف) من خلال Security Groups في Odoo.
        """
        user = request.env.user
        return {
            'success': True,
            'uid': user.id,
            'name': user.name,
            'roles': {
                'is_meter_reader': user.has_group('utility_core.group_utility_meter_reader'),
                'is_collector': user.has_group('utility_core.group_utility_collector'),
                'is_supervisor': user.has_group('utility_core.group_utility_supervisor'),
            }
        }

    # ================================================================
    # استعلام: مشتركي الكاشف الحالي
    # ================================================================
    @http.route('/api/v1/utility/reader/subscribers', type='json',
                auth='user', methods=['POST', 'GET'])
    def reader_subscribers(self, **kwargs):
        """جلب المشتركين المخصصين للكاشف عبر utility.route.user_ids"""
        user = request.env.user

        if not user.has_group('utility_core.group_utility_meter_reader'):
            return self._error(
                'READER_ROLE_REQUIRED',
                'This operation is restricted to meter readers.',
            )

        # البحث عبر utility.route.user_ids مباشرة
        routes = request.env['utility.route'].sudo().search([
            ('user_ids', 'in', [user.id]),
            ('active', '=', True),
        ])
        route_ids = routes.ids

        # fallback عبر utility.meter.reader
        try:
            mr = request.env['utility.meter.reader'].sudo().search(
                [('user_id', '=', user.id)], limit=1
            )
            if mr:
                route_ids = list(set(route_ids + mr.route_ids.ids))
        except Exception:
            pass

        routes = request.env['utility.route'].sudo().browse(route_ids)

        if not route_ids:
            return {
                'success': True,
                'period': None,
                'period_state': None,
                'subscribers': [],
                'count': 0,
                'debug': f'No routes for user {user.login}',
            }

        customers = request.env['utility.customer'].sudo().search([
            ('route_id', 'in', route_ids),
            ('active', '=', True),
        ])

        # Return the server-authoritative work state for the open reading
        # period. This prevents a restarted mobile app from treating an
        # already-submitted subscriber as pending again.
        route_regions = routes.mapped('region_id').ids
        period_domain = [
            ('period_role', '=', 'reading'),
            ('state', '=', 'open'),
            '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id),
        ]
        if route_regions:
            period_domain.extend([
                '|', ('region_ids', '=', False), ('region_ids', 'in', route_regions),
            ])
        current_period = request.env['date.range'].sudo().search(
            period_domain,
            order='date_start desc, id desc',
            limit=1,
        )
        period_data = {
            'id': current_period.id,
            'name': current_period.name,
            'state': current_period.state,
        } if current_period else None

        if not current_period:
            return {
                'success': True,
                'period': None,
                'period_state': None,
                'subscribers': [],
                'count': 0,
                'message': 'No open reading period is available for this reader scope.',
            }

        readings_by_meter = {}
        meter_ids = customers.mapped('meter_id').ids
        if meter_ids and current_period:
            current_readings = request.env['utility.reading'].sudo().search([
                ('meter_id', 'in', meter_ids),
                ('date_range_id', '=', current_period.id),
                ('reading_purpose', '=', 'periodic'),
                ('active', '=', True),
            ], order='reading_date desc, id desc')
            for reading in current_readings:
                readings_by_meter.setdefault(reading.meter_id.id, reading)

        result = []
        for c in customers:
            meter = c.meter_id
            current_reading = readings_by_meter.get(meter.id) if meter else False
            is_returned_for_correction = bool(
                current_reading
                and current_reading.state == 'draft'
                and current_reading.rejected_at
            )
            if is_returned_for_correction:
                reading_status = 'rejected'
            elif current_reading:
                reading_status = 'pending_decision' if current_reading.state == 'draft' else 'read'
            else:
                reading_status = 'pending'
            address = ''
            try:
                address = c.partner_id.contact_address if c.partner_id else ''
            except Exception:
                pass
            result.append({
                'id': c.id,
                'customer_number': c.customer_number or '',
                'name': c.partner_id.name if c.partner_id else c.display_name or '',
                'address': address or '',
                'route_id': c.route_id.id if c.route_id else None,
                'route_name': c.route_id.name if c.route_id else '',
                'meter_id': meter.id if meter else None,
                'meter_number': meter.meter_number if meter else '',
                'last_reading_value': getattr(meter, 'last_reading_value', 0) if meter else 0,
                'reading_status': reading_status,
                'resubmit_reading_id': current_reading.id if is_returned_for_correction else None,
                'rejection_reason': current_reading.rejection_reason if is_returned_for_correction else None,
            })

        return {
            'success': True,
            'period': period_data,
            'period_state': current_period.state,
            'count': len(result),
            'subscribers': result,
        }

    @http.route('/api/v1/utility/reader/reading/submit', type='json',
                auth='user', methods=['POST'])
    def submit_reading(self, **kwargs):
        """
        رفع قراءة فردية لعداد العميل من قبل الكاشف.
        """
        params = kwargs
        
        # Resolve meter
        meter, error_code = self._resolve_meter_identifiers(params)
        if error_code:
            return self._error(error_code or 'METER_NOT_FOUND', 'العداد غير موجود أو البيانات غير مكتملة')

        user = request.env.user
        
        # تحقق من ملكية المسار
        if meter.customer_id.route_id not in user.assigned_route_ids and not user._is_global_utility_scope():
            return self._error('ACCESS_DENIED', 'هذا المشترك لا يقع ضمن المسارات المخصصة لك.')

        reading_value = params.get('reading_value')
        if reading_value is None:
            return self._error('VALIDATION_ERROR', 'قيمة القراءة (reading_value) مطلوبة')

        try:
            reading_value = float(reading_value)
        except ValueError:
            return self._error('VALIDATION_ERROR', 'قيمة القراءة يجب أن تكون رقماً')

        period_id = params.get('period_id')
        if not period_id:
            period = request.env['date.range'].search([
                ('period_role', '=', 'reading'),
                ('state', '=', 'open'),
                '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
            ], order='date_start desc', limit=1)
            period_id = period.id if period else False

        if period_id:
            period = request.env['date.range'].sudo().browse(period_id)
            if not period.exists() or period.state != 'open':
                return self._error('PERIOD_CLOSED', 'الفترة المحددة مغلقة أو غير متاحة للقراءة حالياً')
        else:
            return self._error('PERIOD_NOT_FOUND', 'لم يتم تحديد فترة ولا توجد فترات مفتوحة')

        reading_date = params.get('reading_date', fields.Datetime.now())

        try:
            with request.env.cr.savepoint():
                reading_vals = {
                    'meter_id': meter.id,
                    'customer_id': meter.customer_id.id if meter.customer_id else False,
                    'reading_value': reading_value,
                    'reading_date': reading_date,
                    'reading_purpose': 'periodic',
                    'date_range_id': period_id,
                    'state': 'under_review',  # إرسالها للمراجعة مباشرة
                    'reading_source': 'mobile_app',
                    'remarks': params.get('notes', ''),
                }
                
                reading = request.env['utility.reading'].create(reading_vals)

                # معالجة الصورة إن وُجدت
                image_b64 = params.get('image_b64')
                if image_b64:
                    try:
                        decoded = base64.b64decode(image_b64, validate=True)
                    except (ValueError, binascii.Error):
                        return self._error('INVALID_BASE64', 'بيانات الصورة غير صالحة (Base64 Decode Error)')
                    media_asset = request.env['utility.media.service'].sudo().store_media(
                        file_data=decoded,
                        filename=f"reading_{reading.id}.jpg",
                        mimetype='image/jpeg',
                        reading_id=reading.id,
                        asset_type='meter_reading'
                    )
                    reading.with_context(_bypass_reading_protection=True).write({
                        'image_asset_id': media_asset.id,
                        'image_state': 'pending',
                    })

                return {
                    'success': True,
                    'reading_id': reading.id,
                    'state': reading.state,
                }
        except Exception as e:
            _logger.error("Error submitting reading: %s", str(e))
            return self._error('SYSTEM_ERROR', str(e))

class UtilityReaderApiPatch(http.Controller):


    @http.route(
        '/api/v1/utility/reading/check_period_reading',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def check_period_reading(self, meter_code=None, period_id=None, **kwargs):
        """
        التحقق من وجود قراءة للعداد في الفترة المحددة.
        يُستخدم من التطبيق لمنع القراءة المكررة قبل إدخال بيانات جديدة.

        Returns:
            {
                "has_reading": true/false,
                "reading_value": 1234.0,      # إذا has_reading == true
                "reading_date": "2026-08-01", # إذا has_reading == true
            }
        """
        json_params = getattr(request, 'jsonrequest', None) or {}
        meter_code = meter_code or kwargs.get('meter_code') or json_params.get('meter_code')
        period_id = period_id or kwargs.get('period_id') or json_params.get('period_id')
        if not meter_code or not period_id:
            return {'has_reading': False, 'error': 'meter_code and period_id are required'}

        # البحث عن العداد
        meter = request.env['utility.meter'].sudo().search(
            [('meter_number', '=', meter_code)], limit=1
        )
        if not meter:
            return {'has_reading': False, 'error': f'Meter {meter_code} not found'}

        valid, error_info = UtilityReaderAPI._check_meter_access_scope(meter)
        if not valid:
            code, msg = error_info
            return {'has_reading': False, 'error': msg, 'code': code}

        # البحث عن الفترة
        period = request.env['date.range'].sudo().browse(period_id)
        if not period.exists():
            return {'has_reading': False, 'error': f'Period {period_id} not found'}

        # البحث عن قراءة دورية للعداد في هذه الفترة
        existing = request.env['utility.reading'].sudo().search([
            ('meter_id', '=', meter.id),
            ('date_range_id', '=', period_id),
            ('reading_purpose', '=', 'periodic'),
            ('active', '=', True),
        ], limit=1, order='reading_date desc')

        if existing:
            can_resubmit = bool(existing.state == 'draft' and existing.rejected_at)
            return {
                'has_reading': True,
                'can_resubmit': can_resubmit,
                'reading_value': existing.reading_value,
                'reading_date': str(existing.reading_date) if existing.reading_date else None,
                'reading_id': existing.reading_id,
                'state': existing.state if hasattr(existing, 'state') else 'unknown',
                'resubmit_reading_id': existing.id if can_resubmit else None,
                'rejection_reason': existing.rejection_reason if can_resubmit else None,
            }

        return {'has_reading': False}
