import calendar
from datetime import date, datetime, time, timedelta, timezone
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ..models.utility_date_range import normalize_billing_cadence


class UtilityPeriodGenerator(models.TransientModel):
    _name = 'utility.period.generator'
    _description = 'معالج إنشاء الدورات التشغيلية الموحدة'

    year = fields.Integer(
        string="السنة",
        default=lambda self: fields.Date.today().year,
        required=True
    )
    month = fields.Selection([
        ('1', 'يناير (1)'), ('2', 'فبراير (2)'), ('3', 'مارس (3)'),
        ('4', 'أبريل (4)'), ('5', 'مايو (5)'), ('6', 'يونيو (6)'),
        ('7', 'يوليو (7)'), ('8', 'أغسطس (8)'), ('9', 'سبتمبر (9)'),
        ('10', 'أكتوبر (10)'), ('11', 'نوفمبر (11)'), ('12', 'ديسمبر (12)'),
    ], string="الشهر", default=lambda self: str(fields.Date.today().month), required=True)

    billing_cadence = fields.Selection([
        ('all', 'جميع الدورات (شهري + نصف شهري)'),
        ('monthly', 'شهري فقط'),
        ('semi_monthly', 'نصف شهري فقط'),
    ], string="نوع دورة الفوترة", default='all', required=True)

    override_offsets = fields.Boolean(
        string="تخصيص إزاحات النوافذ التشغيلية",
        default=False,
        help="تفعيل لتحديد إزاحات النوافذ يدوياً بدلاً من الاعتماد على إعدادات نوع الفترة"
    )
    reading_start_offset_days = fields.Integer(
        string="بداية نافذة القراءة (أيام بالنسبة لنهاية الاستهلاك)",
        default=-2
    )
    reading_end_offset_days = fields.Integer(
        string="نهاية نافذة القراءة (أيام بالنسبة لنهاية الاستهلاك)",
        default=3
    )
    payment_start_offset_days = fields.Integer(
        string="بداية نطاق الدفع (أيام من بداية الاستهلاك)",
        default=1,
        help="الفارق بالأيام من date_start لحساب payment_start (1 = اليوم التالي)"
    )
    payment_end_offset_days = fields.Integer(
        string="نهاية نطاق الدفع (أيام من نهاية الاستهلاك)",
        default=1,
        help="الفارق بالأيام من date_end لحساب payment_end (1 = اليوم التالي)"
    )

    def action_generate_periods(self):
        self.ensure_one()
        year = self.year
        month = int(self.month)
        weekday, last_day = calendar.monthrange(year, month)

        DateRange = self.env['date.range'].sudo()
        generated_periods = DateRange

        # حساب الشهر السابق للنظام الآجل
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1
        prev_weekday, prev_last_day = calendar.monthrange(prev_year, prev_month)

        cadences = ['monthly', 'semi_monthly'] if self.billing_cadence == 'all' else [self.billing_cadence]

        for cadence in cadences:
            target_regions = DateRange._get_regions_for_billing_cadence(cadence)
            if not target_regions:
                raise ValidationError(_(
                    "لا توجد مناطق نشطة مرتبطة بدورية الفوترة المحددة (%s)."
                ) % cadence)

            if cadence == 'monthly':
                # نافذة القراءة: خلال شهر الفوترة المختار
                r_start = date(year, month, 1)
                r_end = date(year, month, last_day)
                # فترة الاستهلاك في النظام الآجل: الشهر السابق كاملاً
                c_start = date(prev_year, prev_month, 1)
                c_end = date(prev_year, prev_month, prev_last_day)
                cycle_key = f"MONTHLY-{year:04d}-{month:02d}"
                name = f"شهر {month:02d}-{year:04d}"

                period = self._create_unified_cycle(
                    cycle_key, cadence, r_start, r_end, c_start, c_end, name, target_regions
                )
                generated_periods |= period

            elif cadence == 'semi_monthly':
                # H1: نافذة القراءة من 1 إلى 15 من الشهر المختار
                h1_r_start = date(year, month, 1)
                h1_r_end = date(year, month, 15)
                # فترة الاستهلاك في النظام الآجل: النصف الثاني من الشهر السابق (16 إلى نهاية الشهر السابق)
                h1_c_start = date(prev_year, prev_month, 16)
                h1_c_end = date(prev_year, prev_month, prev_last_day)
                h1_cycle_key = f"SEMI-{year:04d}-{month:02d}-H1"
                h1_name = f"النصف الأول {month:02d}-{year:04d}"

                h1_period = self._create_unified_cycle(
                    h1_cycle_key, cadence, h1_r_start, h1_r_end, h1_c_start, h1_c_end, h1_name, target_regions
                )

                # H2: نافذة القراءة من 16 إلى نهاية الشهر المختار
                h2_r_start = date(year, month, 16)
                h2_r_end = date(year, month, last_day)
                # فترة الاستهلاك في النظام الآجل: النصف الأول من الشهر المختار (1 إلى 15)
                h2_c_start = date(year, month, 1)
                h2_c_end = date(year, month, 15)
                h2_cycle_key = f"SEMI-{year:04d}-{month:02d}-H2"
                h2_name = f"النصف الثاني {month:02d}-{year:04d}"

                h2_period = self._create_unified_cycle(
                    h2_cycle_key, cadence, h2_r_start, h2_r_end, h2_c_start, h2_c_end, h2_name, target_regions,
                    prev_period_id=h1_period.id,
                )

                generated_periods |= h1_period | h2_period

        return {
            'type': 'ir.actions.act_window',
            'name': _('الدورات الموحّدة المنشأة'),
            'res_model': 'date.range',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated_periods.ids)],
        }

    def _create_unified_cycle(
        self, cycle_key, cadence, r_start, r_end, c_start, c_end, name,
        target_regions, prev_period_id=False,
    ):
        """إنشاء سجل دورة موحّد واحد يحمل نطاقَي القراءة والدفع وفترة الاستهلاك الآجل.

        - period_role = 'reading' دائماً للسجلات الجديدة.
        - date_start / date_end = نطاق القراءة الفعلي.
        - consumption_start / consumption_end = دورة الاستهلاك المحسوبة للنظام الآجل.
        - payment_start / payment_end محسوبان من إزاحة القراءة.
        - idempotency: يتحقق بـ cycle_key + period_role='reading' فقط.
        """
        DateRange = self.env['date.range'].sudo()
        DateRangeType = self.env['date.range.type'].sudo()

        period_type = DateRangeType._resolve_period_type(cadence, role='reading')

        # تحديد إزاحات النوافذ
        if self.override_offsets:
            p_start_off = self.payment_start_offset_days
            p_end_off = self.payment_end_offset_days
        else:
            p_start_off = period_type.payment_start_offset_days
            p_end_off = period_type.payment_end_offset_days

        rw_start = self._to_utc_start_of_day(r_start)
        rw_end = self._to_utc_end_of_day(r_end)

        # نطاق الدفع الصريح (حقول Date) محسوب بناءً على تاريخ القراءة
        pay_start = r_start + timedelta(days=p_start_off)
        pay_end = r_end + timedelta(days=p_end_off)

        # Idempotency: البحث بـ cycle_key + period_role='reading' فقط
        existing = DateRange.search([
            ('cycle_key', '=', cycle_key),
            ('period_role', '=', 'reading'),
        ], limit=1)

        if existing:
            if existing.state != 'planned':
                raise ValidationError(_(
                    "الدورة التشغيلية [%s] موجودة مسبقاً وتمر بالحالة العملياتية '%s'. "
                    "لا يمكن إعادة التوليد التلقائي فوق دورة نشطة."
                ) % (cycle_key, existing.state))
            return existing

        period_code = f"CYCLE-{cycle_key}"

        period_vals = {
            'name': name,
            'period_code': period_code,
            'cycle_key': cycle_key,
            'period_role': 'reading',
            'billing_cadence': cadence,
            'region_ids': [(6, 0, target_regions.ids)],
            'type_id': period_type.id,
            'state': 'planned',
            'reading_state': 'planned',
            'collection_state': 'planned',
            # نطاق القراءة الفعلي = date_start / date_end
            'date_start': r_start,
            'date_end': r_end,
            # فترة الاستهلاك في النظام الآجل (تسبق القراءة)
            'consumption_start': c_start,
            'consumption_end': c_end,
            # نافذة القراءة (توقيت دقيق)
            'reading_window_start': rw_start,
            'reading_window_end': rw_end,
            # نطاق الدفع الصريح ونوافذ التحصيل
            'payment_start': pay_start,
            'payment_end': pay_end,
            'payment_window_start': datetime.combine(pay_start, time.min),
            'payment_window_end': datetime.combine(pay_end, time.max.replace(microsecond=0)),
        }
        if prev_period_id:
            period_vals['previous_period_id'] = prev_period_id

        return DateRange.create(period_vals)

    # ------------------------------------------------------------------
    # دعم التوافق العكسي: _create_cycle_pair يُعيد نفس السجل الموحّد مرتَين
    # لكي لا تنكسر أي استدعاءات قديمة خارج هذا الملف.
    # ------------------------------------------------------------------
    def _create_cycle_pair(
        self, cycle_key, cadence, c_start, c_end,
        reading_name, payment_name, target_regions,
        prev_reading_id=False, prev_payment_id=False,
    ):
        """إرجاع توافق عكسي: (unified_cycle, unified_cycle).

        لا تُنشئ سجل دفع منفصل. كلا العنصرين في الزوج يشيران إلى نفس السجل.
        """
        name = reading_name.replace(' (قراءة ومراجعة)', '').replace(' (reading)', '')
        period = self._create_unified_cycle(
            cycle_key, cadence, c_start, c_end, c_start, c_end, name, target_regions,
            prev_period_id=prev_reading_id or prev_payment_id,
        )
        return period, period

    def _to_utc_start_of_day(self, local_date):
        """Convert a local date to a UTC naive datetime at 00:00:00."""
        user_tz = self.env.user.tz or self.env.context.get('tz') or 'UTC'
        local_dt = pytz.timezone(user_tz).localize(datetime.combine(local_date, time.min))
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)

    def _to_utc_end_of_day(self, local_date):
        """Convert a local date to a UTC naive datetime at 23:59:59.999999."""
        user_tz = self.env.user.tz or self.env.context.get('tz') or 'UTC'
        local_dt = pytz.timezone(user_tz).localize(datetime.combine(local_date, time.max))
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)
