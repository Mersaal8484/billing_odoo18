import datetime
from datetime import datetime as _datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

# ثوابت مشتركة
BILLING_PERIOD_TYPES = [
    ('daily',         'يومي'),
    ('weekly',        'أسبوعي'),
    ('semi_monthly',  'نصف شهري'),
    ('monthly',       'شهري'),
    ('quarterly',     'ربع سنوي'),
    ('yearly',        'سنوي'),
    ('biweekly',      'نصف شهري (مستبدل - 15 يوم)'),
]

def normalize_billing_cadence(value):
    """تحويل قيم دورية الفوترة المتقادمة إلى القيمة القياسية ``semi_monthly``."""
    if not value:
        return value
    if value in ('biweekly', 'bi_monthly'):
        return 'semi_monthly'
    return value

WORK_TYPE_SELECTION = [
    ('readings', 'قراءات'),
    ('payment',  'دفع'),
    ('other',    'أخرى'),
]

PERIOD_ROLE_SELECTION = [
    ('reading', 'فترة القراءة والمراجعة'),
    # 'payment' محتفظ به للتوافق العكسي مع السجلات التاريخية فقط
    ('payment', 'فترة السداد والتحصيل (تاريخي)'),
]

PERIOD_STATE_SELECTION = [
    ('planned',    'مخطط'),
    ('open',       'مفتوحة'),
    ('closing',    'قيد الإغلاق والمطابقة'),
    ('closed',     'مغلقة'),
    ('reconciled', 'تمت المطابقة'),
    ('locked',     'مقفلة تاريخياً'),
]

# حالات القراءة المستقلة في السجل الموحد
READING_STATE_SELECTION = [
    ('planned', 'مخططة'),
    ('open',    'مفتوحة للقراءة'),
    ('closing', 'قيد الإغلاق'),
    ('closed',  'مغلقة'),
    ('locked',  'مقفلة تاريخياً'),
]

# حالات التحصيل المستقلة في السجل الموحد
COLLECTION_STATE_SELECTION = [
    ('planned',    'مخطط'),
    ('open',       'مفتوح للتحصيل'),
    ('closing',    'قيد المطابقة'),
    ('reconciled', 'تمت المطابقة'),
    ('locked',     'مقفل تاريخياً'),
]


class DateRangeType(models.Model):
    _inherit = 'date.range.type'

    parent_type_id = fields.Many2one(
        'date.range.type',
        string="النوع الرئيسي",
        help="النوع الأب (مثال: السنة المالية هي الأب للأشهر)"
    )
    fiscal_year = fields.Boolean(string="سنة مالية")
    default_billing_period = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="دورة الفوترة الافتراضية",
        help="تُستخدم تلقائياً عند إنشاء فترة من هذا النوع"
    )
    reading_start_offset_days = fields.Integer(
        string="إزاحة بداية القراءة (أيام قبل نهاية الاستهلاك)",
        default=-2
    )
    reading_end_offset_days = fields.Integer(
        string="إزاحة نهاية القراءة (أيام بعد نهاية الاستهلاك)",
        default=3
    )
    payment_start_offset_days = fields.Integer(
        string="إزاحة بداية التحصيل (أيام بعد نهاية الاستهلاك)",
        default=1
    )
    payment_end_offset_days = fields.Integer(
        string="إزاحة نهاية التحصيل (أيام بعد نهاية الاستهلاك)",
        default=13
    )

    @api.model
    def _resolve_period_type(self, cadence, role='reading'):
        """Return exactly one matching type for the requested cadence."""
        cadence = normalize_billing_cadence(cadence)
        cadence_keys = [cadence, 'biweekly'] if cadence in ('semi_monthly', 'biweekly') else [cadence]
        matches = self.search([
            ('default_billing_period', 'in', cadence_keys),
            ('fiscal_year', '=', False),
            ('allow_overlap', '=', True),
        ])
        if not matches:
            raise ValidationError(_(
                "لم يتم العثور على نوع فترة زمنية (Date Range Type) مناسب يطابق الدورية '%s'."
            ) % cadence)
        if len(matches) > 1:
            raise ValidationError(_(
                "تم العثور على أكثر من نوع فترة زمنية يطابق الدورية '%s'. "
                "يرجى إزالة التكرار في إعدادات أنواع الفترات."
            ) % cadence)
        return matches[0]


class DateRange(models.Model):
    _inherit = 'date.range'

    # ===== التعريف الأساسي والرمز =====
    period_code = fields.Char(
        string="رمز الفترة الفريد",
        copy=False,
        index=True,
        help="رمز معرف فريد للنظام والربط (مثال: CYCLE-SEMI-2026-08-H1)"
    )
    cycle_key = fields.Char(
        string="رمز الدورة التشغيلية",
        index=True,
        copy=False,
        help="رمز فريد لسجل الدورة الموحد (مثال: SEMI-2026-08-H1)"
    )
    period_role = fields.Selection(
        PERIOD_ROLE_SELECTION,
        string="دور الفترة",
        default='reading',
        required=True,
        index=True,
        help="يُبقى بقيمة 'reading' دائماً في السجلات الجديدة. 'payment' محجوز للسجلات التاريخية القديمة فقط."
    )
    billing_cadence = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="دورية الفوترة المستهدفة",
        default='monthly',
        required=True,
        index=True,
    )

    # ===== حالات دورة الحياة (حالة الدورة الموحّدة) =====
    state = fields.Selection(
        PERIOD_STATE_SELECTION,
        string="حالة الفترة",
        default='planned',
        required=True,
        index=True,
        copy=False,
        help="الحالة الإجمالية للدورة. تُستخدم للتحكم في مرحلة التخطيط والفتح والإقفال التاريخي."
    )
    # حالة القراءة المستقلة (تعكس مرحلة جمع القراءات وإغلاقها)
    reading_state = fields.Selection(
        READING_STATE_SELECTION,
        string="حالة القراءة",
        default='planned',
        required=True,
        index=True,
        copy=False,
        help="مستقلة عن حالة التحصيل. الإغلاق هنا لا يوقف التحصيل."
    )
    # حالة التحصيل المستقلة (تعكس مرحلة السداد والمطابقة)
    collection_state = fields.Selection(
        COLLECTION_STATE_SELECTION,
        string="حالة التحصيل",
        default='planned',
        required=True,
        index=True,
        copy=False,
        help="مستقلة عن حالة القراءة. يمكن مطابقة التحصيل بعد إغلاق القراءة."
    )
    reading_closed_at = fields.Datetime(string="تاريخ إغلاق القراءة", readonly=True, copy=False)
    collection_reconciled_at = fields.Datetime(string="تاريخ مطابقة التحصيل", readonly=True, copy=False)

    # ===== نطاق المناطق المعنية =====
    region_ids = fields.Many2many(
        'utility.region',
        'utility_date_range_region_rel',
        'period_id',
        'region_id',
        string="المناطق المشتركة في الفترة",
        domain="[('type', '=', 'region')]",
        help="المناطق التي تنطبق عليها هذه الفترة الزمنية"
    )

    # ===== التواريخ والنوافذ الزمنية التفصيلية =====
    consumption_start = fields.Date(
        string="بداية فترة الاستهلاك",
        help="تاريخ بداية دورة الاستهلاك الفعلية للمشتركين"
    )
    consumption_end = fields.Date(
        string="نهاية فترة الاستهلاك",
        help="تاريخ نهاية دورة الاستهلاك الفعلية للمشتركين"
    )
    reading_window_start = fields.Datetime(
        string="بداية نافذة القراءة والرفع",
        help="الوقت الذي يُسمح فيه للقراء برفع وتوثيق القراءات"
    )
    reading_window_end = fields.Datetime(
        string="نهاية نافذة القراءة والرفع",
        help="الوقت الموعد النهائي المسموح فيه بالرفع المباشر"
    )
    # نطاق الدفع الصريح (حقول تاريخ داخل نفس سجل الدورة)
    payment_start = fields.Date(
        string="بداية نطاق الدفع",
        help="أول يوم مسموح فيه بتسجيل الدفع لهذه الدورة (افتراضياً: date_start + 1 يوم)"
    )
    payment_end = fields.Date(
        string="نهاية نطاق الدفع",
        help="آخر يوم مسموح فيه بتسجيل الدفع لهذه الدورة (افتراضياً: date_end + 1 يوم)"
    )
    payment_window_start = fields.Datetime(
        string="بداية نافذة التحصيل (توقيت دقيق)",
        help="بداية تاريخ التحصيل المسموح لهذه الدورة بالتوقيت الكامل"
    )
    payment_window_end = fields.Datetime(
        string="نهاية نافذة التحصيل (توقيت دقيق)",
        help="نهاية تاريخ التحصيل المسموح لهذه الدورة بالتوقيت الكامل"
    )

    # ===== الربط التاريخي (توافق عكسي — سيُزال في إصدار لاحق) =====
    # هذان الحقلان محتفظ بهما للسجلات التاريخية فقط.
    # في السجلات الجديدة لا تُنشأ سجلات دفع منفصلة.
    reading_period_id = fields.Many2one(
        'date.range',
        string="فترة القراءة المرجعية (تاريخي)",
        domain="[('period_role', '=', 'reading')]",
        index=True,
        ondelete='restrict',
        help="[للتوافق العكسي مع السجلات التاريخية القديمة] فترة القراءة التي تولدت عنها فواتير هذا التحصيل."
    )
    payment_period_ids = fields.One2many(
        'date.range',
        'reading_period_id',
        string="فترات السداد المرتبطة (تاريخي)"
    )

    # ===== الربط الهرمي والسلسلة =====
    parent_id = fields.Many2one(
        'date.range',
        string="الفترة الأب (مثل السنة المالية)",
        index=True,
        help="للهيكلة التقويمية العامة (مثال: السنة المالية للأشهر)"
    )
    child_ids = fields.One2many(
        'date.range', 'parent_id',
        string="الفترات الفرعية"
    )
    previous_period_id = fields.Many2one(
        'date.range',
        string="الفترة السابقة",
        index=True,
        help="الفترة التاريخية السابقة مباشرة لنفس الدورية والنطاق"
    )
    next_period_id = fields.Many2one(
        'date.range',
        string="الفترة التالية",
        compute='_compute_next_period_id',
        store=False
    )

    # ===== التوافق مع الحقول القديمة =====
    billing_period = fields.Selection(
        BILLING_PERIOD_TYPES,
        string="تكرار الفوترة (قديم)",
        compute='_compute_legacy_billing_period',
        inverse='_inverse_legacy_billing_period',
        store=True,
        index=True,
    )
    work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="نوع عمل الفترة (قديم)",
        compute='_compute_legacy_work_type',
        inverse='_inverse_legacy_work_type',
        store=True,
        index=True,
    )
    is_current_period = fields.Boolean(
        string="الفترة النشطة الحالية",
        compute='_compute_is_current_period',
        store=True,
        index=True,
        help="مؤشر توافقي يعبر عن كون الفترة في حالة عمل مفتوحة"
    )

    # ===== تتبع Workflow والتوقيتات =====
    workflow_id = fields.Char(string="مرجع مسار العمل (Workflow Ref)", copy=False)
    workflow_run_id = fields.Char(string="مرجع تشغيل مسار العمل (Workflow Run Ref)", copy=False)
    opened_at = fields.Datetime(string="تاريخ الفتح", readonly=True)
    closed_at = fields.Datetime(string="تاريخ الإغلاق", readonly=True)
    locked_at = fields.Datetime(string="تاريخ الإقفال", readonly=True)

    # ===== المؤشرات المجمعة (Metrics & Aggregations) =====
    expected_accounts = fields.Integer(string="الحسابات المتوقعة", compute='_compute_period_statistics')
    received_readings = fields.Integer(string="القراءات المستلمة", compute='_compute_period_statistics')
    missing_readings = fields.Integer(string="القراءات المفقودة", compute='_compute_period_statistics')
    images_ready = fields.Integer(string="الصور الجاهزة", compute='_compute_period_statistics')
    pending_review = fields.Integer(string="قراءات بانتظار المراجعة", compute='_compute_period_statistics')
    approved_readings = fields.Integer(string="القراءات المعتمدة", compute='_compute_period_statistics')
    rejected_readings = fields.Integer(string="القراءات المرفوضة", compute='_compute_period_statistics')
    bills_generated = fields.Integer(string="الفواتير المنشأة", compute='_compute_period_statistics')
    billed_amount = fields.Monetary(string="إجمالي الفواتير", compute='_compute_period_statistics', currency_field='currency_id')
    accounting_total = fields.Monetary(string="إجمالي الفواتير المحاسبية", compute='_compute_period_statistics', currency_field='currency_id')
    collected_in_window = fields.Monetary(string="التحصيل في النافذة", compute='_compute_period_statistics', currency_field='currency_id')
    outstanding_amount = fields.Monetary(string="المبلغ المتأخر", compute='_compute_period_statistics', currency_field='currency_id')
    collection_rate = fields.Float(string="نسبة التحصيل %", compute='_compute_period_statistics')
    exception_count = fields.Integer(string="عدد الاستثناءات المعلقة", compute='_compute_period_statistics')

    currency_id = fields.Many2one('res.currency', string='العملة', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string="ملاحظات")
    log_ids = fields.One2many('date.range.log', 'period_id', string="سجل التدقيق والمتابعة", readonly=True)
    child_count = fields.Integer(string="عدد الفترات الفرعية", compute='_compute_child_count', store=True)

    _sql_constraints = [
        ('period_code_unique', 'UNIQUE(period_code)', 'رمز الفترة يجب أن يكون فريداً على مستوى النظام!'),
        # cycle_key_role_unique أُزيل: في النموذج الجديد يكفي (cycle_key, company_id) فريداً.
        # cycle_key_role_unique تاريخياً كان UNIQUE(cycle_key, period_role, company_id).
        # تُرك بدون قيد SQL هنا لأن الجدول القديم يحمل سجلات payment تاريخية تشترك بنفس cycle_key.
        # القيد الجديد يُطبَّق عبر _check_cycle_key_unique لمنع تكرار reading بنفس cycle_key.
    ]

    # ===== Compute & Sync Logic =====
    @api.depends('billing_cadence')
    def _compute_legacy_billing_period(self):
        for rec in self:
            rec.billing_period = rec.billing_cadence

    def _inverse_legacy_billing_period(self):
        for rec in self:
            if rec.billing_period:
                cadence = 'semi_monthly' if rec.billing_period == 'biweekly' else rec.billing_period
                rec.billing_cadence = cadence

    @api.depends('period_role')
    def _compute_legacy_work_type(self):
        for rec in self:
            rec.work_type = 'readings' if rec.period_role == 'reading' else 'payment'

    def _inverse_legacy_work_type(self):
        for rec in self:
            if rec.work_type == 'payment':
                rec.period_role = 'payment'
            elif rec.work_type == 'readings':
                rec.period_role = 'reading'

    @api.depends('state')
    def _compute_is_current_period(self):
        for rec in self:
            rec.is_current_period = rec.state in ('open', 'closing')

    @api.depends('child_ids')
    def _compute_child_count(self):
        for rec in self:
            rec.child_count = len(rec.child_ids)

    def _compute_next_period_id(self):
        for rec in self:
            next_p = self.search([('previous_period_id', '=', rec.id)], limit=1)
            rec.next_period_id = next_p.id if next_p else False

    def _compute_period_statistics(self):
        """تجميع الإحصائيات بكفاءة عالية على مستوى الفترة.

        في النموذج الموحّد: يستخدم السجل مباشرة (period_role='reading').
        للسجلات التاريخية (period_role='payment'): يفوّض إلى reading_period_id.
        """
        for rec in self:
            rec.expected_accounts = 0
            rec.received_readings = 0
            rec.missing_readings = 0
            rec.images_ready = 0
            rec.pending_review = 0
            rec.approved_readings = 0
            rec.rejected_readings = 0
            rec.bills_generated = 0
            rec.billed_amount = 0.0
            rec.accounting_total = 0.0
            rec.collected_in_window = 0.0
            rec.outstanding_amount = 0.0
            rec.collection_rate = 0.0
            rec.exception_count = 0

            # السجل الموحد أو التاريخي: target_period هو دائماً سجل القراءة
            target_period = rec if rec.period_role == 'reading' else rec.reading_period_id
            if not target_period:
                continue

            # حسابات القراءات
            readings = self.env['utility.reading'].search([('date_range_id', '=', target_period.id)])
            rec.received_readings = len(readings)
            rec.pending_review = len(readings.filtered(lambda r: r.state == 'under_review'))
            rec.approved_readings = len(readings.filtered(lambda r: r.state in ('approved', 'billed')))
            rec.rejected_readings = len(readings.filtered(lambda r: r.state == 'draft' and r.remarks))
            rec.images_ready = len(readings.filtered(lambda r: bool(r.meter_image)))
            # Billing-specific errors are computed by utility_billing. Core
            # only reports operational reading failures here.
            rec.exception_count = len(readings.filtered(lambda r: r.state == 'error'))

            # حسابات الفواتير والتحصيل
            orders = self.env['sale.order'].search([('date_range_id', '=', target_period.id), ('state', '!=', 'cancel')])
            rec.bills_generated = len(orders)
            rec.billed_amount = sum(orders.mapped('amount_total'))

            invoices = orders.mapped('utility_move_ids').filtered(lambda m: m.state == 'posted')
            rec.accounting_total = sum(invoices.mapped('amount_total'))

            payments = self.env['account.payment'].search([
                ('utility_sale_order_id', 'in', orders.ids),
                ('state', '=', 'posted')
            ])
            rec.collected_in_window = sum(payments.mapped('amount'))
            rec.outstanding_amount = rec.billed_amount - rec.collected_in_window
            if rec.billed_amount > 0:
                rec.collection_rate = round((rec.collected_in_window / rec.billed_amount) * 100.0, 2)

    # ===== Model Constraints =====
    @api.constrains('consumption_start', 'consumption_end')
    def _check_consumption_dates(self):
        for rec in self:
            if rec.consumption_start and rec.consumption_end and rec.consumption_start > rec.consumption_end:
                raise ValidationError(_("تاريخ بداية الاستهلاك يجب أن يكون قبل أو يساوي تاريخ النهاية."))

    @api.constrains('reading_window_start', 'reading_window_end')
    def _check_reading_window_dates(self):
        for rec in self:
            if rec.reading_window_start and rec.reading_window_end and rec.reading_window_start > rec.reading_window_end:
                raise ValidationError(_("تاريخ بداية نافذة القراءة يجب أن يكون قبل تاريخ النهاية."))

    @api.constrains('payment_start', 'payment_end')
    def _check_payment_dates(self):
        """يتحقق من صحة نطاق الدفع داخل السجل الموحّد."""
        for rec in self:
            if rec.payment_start and rec.payment_end and rec.payment_start > rec.payment_end:
                raise ValidationError(_("تاريخ بداية الدفع يجب أن يكون قبل أو يساوي تاريخ نهاية الدفع."))

    @api.constrains('reading_state', 'collection_state', 'state', 'billing_cadence', 'company_id', 'active', 'period_role')
    def _check_single_open_period(self):
        """قيد تشغيلي: يمنع وجود أكثر من فترة قراءة مفتوحة في نفس الوقت،
        وكذلك يمنع وجود أكثر من فترة تحصيل مفتوحة في نفس الوقت لنفس الدورية والشركة.
        """
        cadence_labels = dict(BILLING_PERIOD_TYPES)
        for rec in self:
            if not rec.active or rec.period_role != 'reading':
                continue
            cadence = normalize_billing_cadence(rec.billing_cadence)
            cadence_name = cadence_labels.get(rec.billing_cadence, rec.billing_cadence)

            # 1. التحقق من فترة القراءة: فترة واحدة مفتوحة فقط
            if rec.reading_state == 'open':
                duplicate_reading = self.search([
                    ('id', '!=', rec.id),
                    ('active', '=', True),
                    ('period_role', '=', 'reading'),
                    ('company_id', '=', rec.company_id.id),
                    ('reading_state', '=', 'open'),
                ]).filtered(
                    lambda r: normalize_billing_cadence(r.billing_cadence) == cadence
                )
                if duplicate_reading:
                    other = duplicate_reading[0]
                    raise ValidationError(_(
                        "لا يمكن فتح أكثر من فترة قراءة في نفس الوقت لنفس الدورية (%s).\n"
                        "الفترة المفتوحة حالياً: [%s - %s].\n"
                        "يجب إغلاق فترة القراءة الحالية أولاً قبل فتح فترة جديدة."
                    ) % (cadence_name, other.period_code or other.cycle_key or other.name, other.name))

            # 2. التحقق من فترة التحصيل: فترة واحدة مفتوحة فقط
            if rec.collection_state == 'open':
                duplicate_collection = self.search([
                    ('id', '!=', rec.id),
                    ('active', '=', True),
                    ('period_role', '=', 'reading'),
                    ('company_id', '=', rec.company_id.id),
                    ('collection_state', '=', 'open'),
                ]).filtered(
                    lambda r: normalize_billing_cadence(r.billing_cadence) == cadence
                )
                if duplicate_collection:
                    other = duplicate_collection[0]
                    raise ValidationError(_(
                        "لا يمكن فتح أكثر من فترة تحصيل في نفس الوقت لنفس الدورية (%s).\n"
                        "فترة التحصيل المفتوحة حالياً: [%s - %s].\n"
                        "يجب إغلاق أو مطابقة فترة التحصيل الحالية أولاً قبل فتح فترة تحصيل جديدة."
                    ) % (cadence_name, other.period_code or other.cycle_key or other.name, other.name))

    @api.constrains('cycle_key', 'period_role', 'company_id')
    def _check_cycle_key_unique(self):
        """يمنع إنشاء سجل دورة موحّد مكرر بنفس cycle_key.

        السجلات التاريخية (period_role='payment') مستثناة لأنها تشترك بنفس cycle_key
        مع سجل القراءة القديم — وهو سلوك مقصود للتوافق العكسي.
        """
        for rec in self.filtered(lambda r: r.cycle_key and r.period_role == 'reading'):
            duplicate = self.search([
                ('cycle_key', '=', rec.cycle_key),
                ('period_role', '=', 'reading'),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "يوجد سجل دورة قراءة بنفس رمز الدورة [%s]. يجب أن يكون رمز الدورة فريداً لكل شركة."
                ) % rec.cycle_key)

    @api.constrains('period_role', 'reading_period_id', 'billing_cadence')
    def _check_payment_reading_link(self):
        """يُطبَّق فقط على السجلات التاريخية (period_role='payment').

        في السجلات الجديدة الموحّدة period_role='reading' دائماً
        ولا يوجد reading_period_id؛ القيد لا ينطبق عليها.
        """
        for rec in self:
            if rec.period_role == 'payment':
                if not rec.reading_period_id:
                    raise ValidationError(_("[سجل تاريخي] يجب ربط فترة السداد بفترة قراءة صريحة."))
                if rec.reading_period_id.period_role != 'reading':
                    raise ValidationError(_("[سجل تاريخي] فترة القراءة المرتبطة يجب أن تكون من دور قراءة."))
                if (
                    normalize_billing_cadence(rec.billing_cadence)
                    != normalize_billing_cadence(rec.reading_period_id.billing_cadence)
                ):
                    raise ValidationError(_("[سجل تاريخي] دورية فترة السداد يجب أن تطابق دورية فترة القراءة."))
                if rec.region_ids != rec.reading_period_id.region_ids:
                    raise ValidationError(_("[سجل تاريخي] نطاق مناطق فترة السداد يجب أن يطابق فترة القراءة."))

    @api.model
    def _normalize_cadence(self, cadence):
        return normalize_billing_cadence(cadence)

    @api.constrains('region_ids', 'billing_cadence')
    def _check_region_cadence_consistency(self):
        for rec in self:
            if rec.region_ids:
                p_cadence = normalize_billing_cadence(rec.billing_cadence)
                mismatched = rec.region_ids.filtered(
                    lambda r: r.recurring_rule_type and normalize_billing_cadence(r.recurring_rule_type) != p_cadence
                )
                if mismatched:
                    names = ", ".join(mismatched.mapped('name'))
                    raise ValidationError(_(
                        "دورية المناطق التابعة (%s) لا تطابق دورية الفترة (%s)."
                    ) % (names, rec.billing_cadence))

    @api.constrains('period_code', 'billing_cadence')
    def _check_period_code_cadence_consistency(self):
        """يمنع حفظ سجل يكون فيه period_code يدل على دورية معينة
        لكن billing_cadence يحمل قيمة مغايرة.

        القواعد المعرّفة:
          SE*, READ-SEMI-*, PAY-SEMI-*  →  semi_monthly
          READ-MONTHLY-*, PAY-MONTHLY-*, MONTHLY-*  →  monthly

        إذا كانت البادئة غير معروفة لا يُطبَّق أي قيد (مرونة للمستقبل).
        يستخدم normalize_billing_cadence لمعالجة المرادفات القديمة.
        """
        CODE_CADENCE_MAP = [
            (('SE',), 'semi_monthly'),
            (('READ-SEMI-', 'PAY-SEMI-'), 'semi_monthly'),
            (('READ-MONTHLY-', 'PAY-MONTHLY-', 'MONTHLY-'), 'monthly'),
        ]
        for rec in self:
            if not rec.period_code:
                continue
            code = rec.period_code.upper()
            expected_cadence = None
            for prefixes, cadence in CODE_CADENCE_MAP:
                if any(code.startswith(p) for p in prefixes):
                    expected_cadence = cadence
                    break
            if expected_cadence is None:
                continue  # بادئة غير معروفة — لا قيد ينطبق
            actual = normalize_billing_cadence(rec.billing_cadence)
            if actual != expected_cadence:
                raise ValidationError(_(
                    "رمز الفترة '%s' يدل على دورية '%s' "
                    "لكن دورية الفوترة المحفوظة هي '%s'.\n"
                    "تأكد من ضبط دورية الفوترة الصحيحة قبل الحفظ."
                ) % (rec.period_code, expected_cadence, rec.billing_cadence))

    # ===== Region Scope Auto-Population =====

    @api.model
    def _get_regions_for_billing_cadence(self, cadence):
        """إرجاع جميع المناطق الرئيسية النشطة التي تطابق الدورية المحدّدة.

        يستخدم SQL domain مباشرة — بدون تحميل كل المناطق للذاكرة.
        semi_monthly يشمل biweekly القديم (مترادفان فعلياً).
        """
        cadence = normalize_billing_cadence(cadence)
        if not cadence:
            return self.env['utility.region']
        domain = [('type', '=', 'region'), ('active', '=', True)]
        if cadence == 'semi_monthly':
            # biweekly مرادف قديم لـ semi_monthly — نجمعهما في نفس الاستعلام
            domain.append(('recurring_rule_type', 'in', ['semi_monthly', 'biweekly']))
        else:
            domain.append(('recurring_rule_type', '=', cadence))
        return self.env['utility.region'].search(domain)


    @api.onchange('billing_cadence', 'period_role')
    def _onchange_billing_cadence_regions(self):
        """ملء region_ids تلقائياً عند تغيير الدورية — للقراءة فقط.

        Payment Period: مناطقه مشتقة حصراً من reading_period_id.
        لا نحسب مناطقه من billing_cadence لأن ذلك يكسر الـ Snapshot.
        """
        for rec in self:
            # Payment يرث فقط من reading_period_id — لا تُعيد الحساب هنا
            if rec.period_role == 'payment':
                continue
            # نحمي الفترات التاريخية: planned أو سجل جديد فقط
            if rec.state and rec.state != 'planned':
                continue
            rec.region_ids = rec._get_regions_for_billing_cadence(rec.billing_cadence)


    @api.onchange('reading_period_id')
    def _onchange_reading_period_scope(self):
        """فترة السداد ترث نطاق المناطق والدورية من فترة القراءة المرتبطة.

        لا نُعيد البحث عن المناطق — نأخذ Snapshot كاملاً من فترة القراءة."""
        for rec in self:
            if rec.period_role != 'payment':
                continue
            if rec.reading_period_id:
                rec.billing_cadence = rec.reading_period_id.billing_cadence
                rec.region_ids = rec.reading_period_id.region_ids

    @api.model_create_multi
    def create(self, vals_list):
        """عند إنشاء فترة قراءة بدون region_ids صريحة، تملأ تلقائياً حسب الدورية.

        لا يؤثر على الفترات التاريخية — يعمل فقط عند إنشاء سجلات جديدة.
        Payment Period: يرث النطاق من reading_period_id إذا لم تُحدَّد مناطق."""
        for vals in vals_list:
            role = vals.get('period_role', 'reading')
            raw_cadence = vals.get('billing_cadence') or vals.get('billing_period') or 'monthly'
            cadence = normalize_billing_cadence(raw_cadence)
            if 'billing_cadence' not in vals:
                vals['billing_cadence'] = cadence

            if not vals.get('type_id'):
                period_type = self.env['date.range.type']._resolve_period_type(cadence, role)
                vals['type_id'] = period_type.id

            type_rec = self.env['date.range.type'].browse(vals['type_id'])
            is_fiscal = type_rec.fiscal_year

            # Ensure date_start and date_end are populated
            if not vals.get('date_start'):
                if role == 'reading' and vals.get('consumption_start'):
                    vals['date_start'] = vals['consumption_start']
                elif role == 'payment' and vals.get('payment_window_start'):
                    vals['date_start'] = fields.Date.to_date(vals['payment_window_start'])
                else:
                    vals['date_start'] = fields.Date.today().replace(day=1)

            if not vals.get('date_end'):
                if role == 'reading' and vals.get('consumption_end'):
                    vals['date_end'] = vals['consumption_end']
                elif role == 'payment' and vals.get('payment_window_end'):
                    vals['date_end'] = fields.Date.to_date(vals['payment_window_end'])
                else:
                    vals['date_end'] = fields.Date.today().replace(day=28)

            # مزامنة تلقائية لنطاق القراءة مع نافذة القراءة وفترة الاستهلاك
            if vals.get('date_start') and not vals.get('reading_window_start'):
                d_s = fields.Date.to_date(vals['date_start'])
                vals['reading_window_start'] = datetime.datetime.combine(d_s, datetime.time.min) if d_s else False
            elif vals.get('reading_window_start') and not vals.get('date_start'):
                vals['date_start'] = fields.Date.to_date(vals['reading_window_start'])

            if vals.get('date_end') and not vals.get('reading_window_end'):
                d_e = fields.Date.to_date(vals['date_end'])
                vals['reading_window_end'] = datetime.datetime.combine(d_e, datetime.time.max.replace(microsecond=0)) if d_e else False
            elif vals.get('reading_window_end') and not vals.get('date_end'):
                vals['date_end'] = fields.Date.to_date(vals['reading_window_end'])

            if not vals.get('consumption_start') and vals.get('date_start'):
                vals['consumption_start'] = vals['date_start']
            if not vals.get('consumption_end') and vals.get('date_end'):
                vals['consumption_end'] = vals['date_end']

            # مزامنة تلقائية لنطاق الدفع (Date) مع نافذة التحصيل (Datetime)
            if vals.get('payment_start') and not vals.get('payment_window_start'):
                p_s = fields.Date.to_date(vals['payment_start'])
                vals['payment_window_start'] = datetime.datetime.combine(p_s, datetime.time.min) if p_s else False
            elif vals.get('payment_window_start') and not vals.get('payment_start'):
                vals['payment_start'] = fields.Date.to_date(vals['payment_window_start'])

            if vals.get('payment_end') and not vals.get('payment_window_end'):
                p_e = fields.Date.to_date(vals['payment_end'])
                vals['payment_window_end'] = datetime.datetime.combine(p_e, datetime.time.max.replace(microsecond=0)) if p_e else False
            elif vals.get('payment_window_end') and not vals.get('payment_end'):
                vals['payment_end'] = fields.Date.to_date(vals['payment_window_end'])

            if role == 'reading' and not is_fiscal and 'region_ids' not in vals:
                regions = self._get_regions_for_billing_cadence(cadence)
                if regions:
                    vals['region_ids'] = [(6, 0, regions.ids)]
            elif role == 'payment' and 'region_ids' not in vals:
                reading_period_id = vals.get('reading_period_id')
                if reading_period_id:
                    reading_period = self.browse(reading_period_id).exists()
                    if reading_period and reading_period.region_ids:
                        vals['region_ids'] = [(6, 0, reading_period.region_ids.ids)]
                        vals['billing_cadence'] = reading_period.billing_cadence
        return super().create(vals_list)

    def action_sync_regions_by_cadence(self):
        """مزامنة يدوية لنطاق المناطق للسجلات المخطّطة (planned) فقط.

        يستخدمه المدير لإصلاح سجلات موجودة بدون تعيين المناطق الصحيح.
        القيد: يرفض أي فترة ليست في حالة 'مخطط'."""
        for rec in self:
            if rec.state != 'planned':
                raise ValidationError(_(
                    "يمكن مزامنة نطاق المناطق فقط عندما تكون الفترة في حالة مخطط.\n"
                    "الفترة '%s' حالتها الحالية: '%s'."
                ) % (rec.name or rec.period_code, dict(PERIOD_STATE_SELECTION).get(rec.state, rec.state)))

            if rec.period_role == 'payment':
                if not rec.reading_period_id:
                    raise ValidationError(_(
                        "فترة السداد '%s' يجب أن تكون مرتبطة بفترة قراءة قبل مزامنة النطاق."
                    ) % (rec.name or rec.period_code))
                rec.write({
                    'billing_cadence': rec.reading_period_id.billing_cadence,
                    'region_ids': [(6, 0, rec.reading_period_id.region_ids.ids)],
                })
            else:
                regions = rec._get_regions_for_billing_cadence(rec.billing_cadence)
                rec.write({
                    'region_ids': [(6, 0, regions.ids)],
                })
        return True

    # ===== Historical Scope Protection =====

    # حقول النطاق محمية بعد مرحلة التخطيط — لا تعديل على فترات تاريخية
    _SCOPE_PROTECTED_FIELDS = frozenset({
        'cycle_key', 'region_ids', 'billing_cadence', 'period_role', 'reading_period_id',
    })
    # حقول نطاق الدفع محمية بعد فتح الدورة للتشغيل
    _PAYMENT_SCOPE_PROTECTED_FIELDS = frozenset({
        'payment_start', 'payment_end', 'payment_window_start', 'payment_window_end',
    })
    _PAYMENT_SCOPE_MUTABLE_STATES = frozenset({'planned', 'open'})
    # الحالة الوحيدة التي يُسمح فيها بتعديل النطاق
    _SCOPE_MUTABLE_STATES = frozenset({'planned'})

    def write(self, vals):
        """Model Guard: يحمي حقول النطاق الجغرافي بعد مرحلة التخطيط.

        القاعدة:
        - region_ids / billing_cadence / period_role / reading_period_id
          لا تُعدَّل بعد state != planned — حتى عبر API أو RPC.
        - payment_start / payment_end محميان بعد إغلاق القراءة (reading_state='closed').
        Context bypass: _bypass_period_scope_protection يُستخدم داخلياً فقط.
        """
        vals = dict(vals)

        # مزامنة تلقائية لنطاق القراءة مع نافذة القراءة وفترة الاستهلاك
        if 'date_start' in vals and 'reading_window_start' not in vals:
            d_s = fields.Date.to_date(vals['date_start'])
            vals['reading_window_start'] = datetime.datetime.combine(d_s, datetime.time.min) if d_s else False
        elif 'reading_window_start' in vals and 'date_start' not in vals:
            vals['date_start'] = fields.Date.to_date(vals['reading_window_start'])

        if 'date_end' in vals and 'reading_window_end' not in vals:
            d_e = fields.Date.to_date(vals['date_end'])
            vals['reading_window_end'] = datetime.datetime.combine(d_e, datetime.time.max.replace(microsecond=0)) if d_e else False
        elif 'reading_window_end' in vals and 'date_end' not in vals:
            vals['date_end'] = fields.Date.to_date(vals['reading_window_end'])

        # مزامنة تلقائية لنطاق الدفع (Date) مع نافذة التحصيل (Datetime) عند التعديل
        if 'payment_start' in vals and 'payment_window_start' not in vals:
            p_s = fields.Date.to_date(vals['payment_start'])
            vals['payment_window_start'] = datetime.datetime.combine(p_s, datetime.time.min) if p_s else False
        elif 'payment_window_start' in vals and 'payment_start' not in vals:
            vals['payment_start'] = fields.Date.to_date(vals['payment_window_start'])

        if 'payment_end' in vals and 'payment_window_end' not in vals:
            p_e = fields.Date.to_date(vals['payment_end'])
            vals['payment_window_end'] = datetime.datetime.combine(p_e, datetime.time.max.replace(microsecond=0)) if p_e else False
        elif 'payment_window_end' in vals and 'payment_end' not in vals:
            vals['payment_end'] = fields.Date.to_date(vals['payment_window_end'])
        scope_changed = set(vals.keys()) & self._SCOPE_PROTECTED_FIELDS
        if scope_changed and not (
            self.env.context.get('_bypass_period_scope_protection') or
            self.env.context.get('install_mode') or
            self.env.context.get('module')
        ):
            for rec in self:
                if rec.type_id and rec.type_id.fiscal_year:
                    continue
                if rec.state not in self._SCOPE_MUTABLE_STATES:
                    raise ValidationError(_(
                        "لا يمكن تعديل نطاق الفترة [%s] بعد مرحلة التخطيط.\n"
                        "الحقول المحمية: %s\n"
                        "الحالة الحالية: %s"
                    ) % (
                        rec.name or rec.period_code,
                        ', '.join(sorted(scope_changed)),
                        dict(PERIOD_STATE_SELECTION).get(rec.state, rec.state),
                    ))
        # حماية نطاق الدفع بعد إغلاق القراءة
        payment_scope_changed = set(vals.keys()) & self._PAYMENT_SCOPE_PROTECTED_FIELDS
        if payment_scope_changed and not (
            self.env.context.get('_bypass_period_scope_protection') or
            self.env.context.get('install_mode') or
            self.env.context.get('module')
        ):
            for rec in self:
                if rec.reading_state == 'closed':
                    raise ValidationError(_(
                        "لا يمكن تعديل نطاق الدفع [%s] بعد إغلاق القراءة.\n"
                        "استخدم إجراء إعادة الفتح المسجل إذا كان التعديل ضرورياً."
                    ) % (rec.name or rec.period_code))
        planned_readings = self.filtered(
            lambda r: r.state == 'planned' and r.period_role == 'reading'
        )
        if planned_readings:
            if 'billing_cadence' in vals or 'region_ids' in vals:
                new_cadence = vals.get('billing_cadence', planned_readings[0].billing_cadence)
                regions = planned_readings[0]._get_regions_for_billing_cadence(new_cadence)
                vals['region_ids'] = [(6, 0, regions.ids)]
        payment_periods = self.filtered(lambda r: r.period_role == 'payment' and 'reading_period_id' in vals)
        if payment_periods:
            reading_period = self.env['date.range'].browse(vals['reading_period_id']).exists()
            if reading_period:
                vals['billing_cadence'] = reading_period.billing_cadence
                vals['region_ids'] = [(6, 0, reading_period.region_ids.ids)]
        return super().write(vals)

    # ===== Audit Helper =====

    def _log_state_transition(self, old_state, new_state, reason=False):
        for rec in self:
            self.env['date.range.log'].sudo().create({
                'period_id': rec.id,
                'old_state': old_state,
                'new_state': new_state,
                'user_id': self.env.uid,
                'timestamp': fields.Datetime.now(),
                'reason': reason or _("تغيير حالة الدورة التشغيلية"),
                'workflow_id': rec.workflow_id,
                'workflow_run_id': rec.workflow_run_id,
            })

    # ===== State Machine Transition Matrix Validation =====
    def _validate_state_transition(self, allowed_states, target_state_label):
        self.ensure_one()
        if self.state not in allowed_states:
            labels = dict(PERIOD_STATE_SELECTION)
            allowed_labels = ", ".join([str(labels.get(s, s)) for s in allowed_states])
            current_label = labels.get(self.state, self.state)
            raise ValidationError(_(
                "الانتقال التسلسلي إلى '%s' غير مسموح من الحالة الحالية '%s'. "
                "الحالات المسموحة للانتقال إليها: [%s]."
            ) % (target_state_label, current_label, allowed_labels))

    # ===== State Machine Action Methods =====

    def action_open_period(self):
        """فتح الدورة: تُفتح حالة state → open وتُهيأ reading_state وcollection_state."""
        for rec in self:
            if rec.state == 'locked':
                raise ValidationError(_("لا يمكن فتح فترة مقفلة تاريخياً (locked)."))
            rec._validate_state_transition(['planned'], _('فتح الفترة'))
            cadence = normalize_billing_cadence(rec.billing_cadence)
            cadence_name = dict(BILLING_PERIOD_TYPES).get(rec.billing_cadence, rec.billing_cadence)

            # التحقق من عدم وجود دورة قراءة مفتوحة لنفس الدورية
            open_reading = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('period_role', '=', 'reading'),
                ('company_id', '=', rec.company_id.id),
                ('reading_state', '=', 'open'),
            ]).filtered(lambda r: normalize_billing_cadence(r.billing_cadence) == cadence)
            if open_reading:
                other = open_reading[0]
                raise ValidationError(_(
                    "لا يمكن فتح دورة جديدة للعمليات: توجد بالفعل فترة قراءة مفتوحة لنفس الدورية (%s): [%s - %s].\n"
                    "يجب إغلاق فترة القراءة الحالية أولاً قبل فتح فترة جديدة."
                ) % (cadence_name, other.period_code or other.cycle_key or other.name, other.name))

            # فحص إمكانية فتح التحصيل بالتزامن
            open_collection = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('period_role', '=', 'reading'),
                ('company_id', '=', rec.company_id.id),
                ('collection_state', '=', 'open'),
            ]).filtered(lambda r: normalize_billing_cadence(r.billing_cadence) == cadence)

            target_collection_state = 'planned' if open_collection else 'open'

            old_s = rec.state
            write_vals = {
                'state': 'open',
                'reading_state': 'open',
                'collection_state': target_collection_state,
                'opened_at': fields.Datetime.now() if not rec.opened_at else rec.opened_at,
            }
            if old_s == 'planned':
                final_regions = rec._get_regions_for_billing_cadence(rec.billing_cadence)
                if not final_regions:
                    raise ValidationError(_(
                        "لا توجد مناطق نشطة تطابق دورة الفوترة '%s'."
                    ) % rec.billing_cadence)
                write_vals['region_ids'] = [(6, 0, final_regions.ids)]
                # ضبط نطاق الدفع الافتراضي إذا لم يُحدَّد
                if not rec.payment_start and rec.date_start:
                    write_vals['payment_start'] = rec.date_start + datetime.timedelta(days=1)
                if not rec.payment_end and rec.date_end:
                    write_vals['payment_end'] = rec.date_end + datetime.timedelta(days=1)
            rec.with_context(_bypass_period_scope_protection=True).write(write_vals)
            rec._log_state_transition(old_s, 'open', _("فتح الدورة للعمليات التشغيلية"))

    def action_open_reading(self):
        """فتح أو إعادة فتح القراءة فقط (reading_state → open) دون المساس بالتحصيل."""
        for rec in self:
            if rec.reading_state == 'locked':
                raise ValidationError(_("لا يمكن إعادة فتح قراءة مقفلة تاريخياً."))
            cadence = normalize_billing_cadence(rec.billing_cadence)
            cadence_name = dict(BILLING_PERIOD_TYPES).get(rec.billing_cadence, rec.billing_cadence)
            open_reading = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('period_role', '=', 'reading'),
                ('company_id', '=', rec.company_id.id),
                ('reading_state', '=', 'open'),
            ]).filtered(lambda r: normalize_billing_cadence(r.billing_cadence) == cadence)
            if open_reading:
                other = open_reading[0]
                raise ValidationError(_(
                    "توجد بالفعل فترة قراءة مفتوحة لنفس الدورية (%s): [%s - %s]. "
                    "يجب إغلاق فترة القراءة المفتوحة أولاً."
                ) % (cadence_name, other.period_code or other.cycle_key or other.name, other.name))
            old_rs = rec.reading_state
            write_vals = {'reading_state': 'open'}
            if rec.state == 'planned':
                write_vals['state'] = 'open'
                if not rec.opened_at:
                    write_vals['opened_at'] = fields.Datetime.now()
                final_regions = rec._get_regions_for_billing_cadence(rec.billing_cadence)
                if final_regions:
                    write_vals['region_ids'] = [(6, 0, final_regions.ids)]
                if not rec.payment_start and rec.date_start:
                    write_vals['payment_start'] = rec.date_start + datetime.timedelta(days=1)
                if not rec.payment_end and rec.date_end:
                    write_vals['payment_end'] = rec.date_end + datetime.timedelta(days=1)
            elif rec.state in ('closed', 'closing'):
                write_vals['state'] = 'open'
            rec.write(write_vals)
            rec._log_state_transition(old_rs, 'open', _("فتح/إعادة فتح القراءة للعمليات"))

    def action_open_payment(self):
        """فتح أو إعادة فتح التحصيل (collection_state → open)."""
        for rec in self:
            if rec.collection_state == 'locked':
                raise ValidationError(_("لا يمكن إعادة فتح تحصيل مقفل تاريخياً."))
            cadence = normalize_billing_cadence(rec.billing_cadence)
            cadence_name = dict(BILLING_PERIOD_TYPES).get(rec.billing_cadence, rec.billing_cadence)
            open_collection = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('period_role', '=', 'reading'),
                ('company_id', '=', rec.company_id.id),
                ('collection_state', '=', 'open'),
            ]).filtered(lambda r: normalize_billing_cadence(r.billing_cadence) == cadence)
            if open_collection:
                other = open_collection[0]
                raise ValidationError(_(
                    "توجد بالفعل فترة تحصيل مفتوحة لنفس الدورية (%s): [%s - %s]. "
                    "يجب إغلاق أو مطابقة فترة التحصيل المفتوحة أولاً قبل فتح فترة تحصيل أخرى."
                ) % (cadence_name, other.period_code or other.cycle_key or other.name, other.name))
            old_cs = rec.collection_state
            write_vals = {'collection_state': 'open'}
            if rec.state == 'planned':
                write_vals['state'] = 'open'
                if not rec.opened_at:
                    write_vals['opened_at'] = fields.Datetime.now()
                final_regions = rec._get_regions_for_billing_cadence(rec.billing_cadence)
                if final_regions:
                    write_vals['region_ids'] = [(6, 0, final_regions.ids)]
                if not rec.payment_start and rec.date_start:
                    write_vals['payment_start'] = rec.date_start + datetime.timedelta(days=1)
                if not rec.payment_end and rec.date_end:
                    write_vals['payment_end'] = rec.date_end + datetime.timedelta(days=1)
            elif rec.state == 'closed':
                write_vals['state'] = 'closing'
            rec.write(write_vals)
            rec._log_state_transition(old_cs, 'open', _("فتح/إعادة فتح التحصيل للعمليات"))

    def action_start_closing(self):
        """بدء إغلاق القراءة فقط: reading_state → closing. لا يُغلق التحصيل."""
        for rec in self:
            if rec.reading_state not in ('open',):
                raise ValidationError(_(
                    "لا يمكن بدء إغلاق القراءة من الحالة الحالية '%s'. المتطلب: مفتوحة."
                ) % dict(READING_STATE_SELECTION).get(rec.reading_state, rec.reading_state))
            old_rs = rec.reading_state
            rec.write({'reading_state': 'closing'})
            rec._log_state_transition(old_rs, 'closing', _("بدء إغلاق القراءة — التحصيل لا يزال مفتوحاً"))

    def action_close_reading(self):
        """إغلاق القراءة: reading_state → closed بعد استيفاء متطلبات الاكتمال."""
        for rec in self:
            if rec.reading_state not in ('open', 'closing'):
                raise ValidationError(_(
                    "لا يمكن إغلاق القراءة من الحالة '%s'."
                ) % dict(READING_STATE_SELECTION).get(rec.reading_state, rec.reading_state))
            rec._validate_period_closing_reconciliation()
            old_rs = rec.reading_state
            rec.write({
                'reading_state': 'closed',
                'reading_closed_at': fields.Datetime.now(),
            })
            # تحديث الحالة الرئيسية (state) إلى closing للإشارة
            if rec.state == 'open':
                rec.write({'state': 'closing'})
            rec._log_state_transition(old_rs, 'closed', _("إغلاق القراءة — التحصيل لا يزال مفتوحاً"))

    def action_close_payment(self):
        """إغلاق التحصيل (للسجلات التاريخية period_role='payment' فقط)."""
        for rec in self:
            if rec.period_role != 'payment':
                raise ValidationError(_("استخدم action_reconcile_collection للسجلات الموحّدة."))
            rec._validate_state_transition(['open', 'closing'], _('إغلاق التحصيل التاريخي'))
            old_s = rec.state
            rec.write({'state': 'closing'})
            rec._log_state_transition(old_s, 'closing', _("بدء إغلاق فترة التحصيل التاريخية"))

    def action_reconcile_collection(self):
        """مطابقة التحصيل على السجل الموحّد: collection_state → reconciled."""
        for rec in self:
            if rec.period_role == 'payment':
                # السجلات التاريخية: استدعاء action_reconcile_payment القديم
                return rec.action_reconcile_payment()
            if rec.collection_state not in ('open', 'closing'):
                raise ValidationError(_(
                    "لا يمكن مطابقة التحصيل من الحالة '%s'."
                ) % dict(COLLECTION_STATE_SELECTION).get(rec.collection_state, rec.collection_state))
            old_cs = rec.collection_state
            rec.write({
                'collection_state': 'reconciled',
                'collection_reconciled_at': fields.Datetime.now(),
            })
            # إذا أُغلقت القراءة وتمت مطابقة التحصيل — نُغلق الدورة بالكامل
            if rec.reading_state == 'closed':
                rec.write({'state': 'closed', 'closed_at': fields.Datetime.now()})
            rec._log_state_transition(old_cs, 'reconciled', _("مطابقة التحصيل — الدورة مكتملة"))

    def _validate_period_closing_reconciliation(self):
        """فحص ومطابقة جميع متطلبات إغلاق القراءة لضمان سلامة العمليات."""
        self.ensure_one()
        errors = []

        # 1. دفعات القراءات قيد الرفع والمعالجة
        batches = self.env['utility.reading.batch'].search([
            ('date_range_id', '=', self.id),
            ('state', 'in', ('uploaded', 'processing'))
        ])
        if batches:
            errors.append(_("توجد %d دفعة رفع قراءات ما زالت قيد المعالجة أو الرفع.") % len(batches))

        # 2. قراءات غير معتمدة أو بها أخطاء
        pending_readings = self.env['utility.reading'].search([
            ('date_range_id', '=', self.id),
            ('state', 'in', ('draft', 'under_review', 'queued', 'error'))
        ])
        if pending_readings:
            errors.append(_("توجد %d قراءة غير معتمدة أو بها أخطاء غير محلولة.") % len(pending_readings))

        # 3. قراءات معتمدة لم تُفوتر بعد
        unbilled_approved = self.env['utility.reading'].search([
            ('date_range_id', '=', self.id),
            ('reading_purpose', '=', 'periodic'),
            ('state', '=', 'approved'),
        ])
        if unbilled_approved:
            errors.append(_("توجد %d قراءة معتمدة لم يتم إنشاء فواتير لها بعد.") % len(unbilled_approved))

        # 4. فواتير كهرباء لم يتم تظهير فواتير محاسبية لها
        unposted_orders = self.env['sale.order'].search([
            ('date_range_id', '=', self.id),
            ('state', '!=', 'cancel'),
        ])
        for order in unposted_orders:
            if not order.utility_move_ids or any(m.state != 'posted' for m in order.utility_move_ids):
                errors.append(_("أمر البيع %s لا يحتوي على فاتورة محاسبية مرحّلة.") % order.name)

        if errors:
            raise ValidationError(_("لا يمكن إغلاق القراءة بسبب:\n- ") + "\n- ".join(errors))

    def action_close_period(self):
        """إغلاق الدورة الكاملة: state → closed (للتوافق العكسي مع الكود القديم)."""
        for rec in self:
            if rec.period_role == 'payment':
                raise ValidationError(_("فترة التحصيل لا تُغلق إلى closed؛ استخدم مطابقة التحصيل."))
            rec._validate_state_transition(['closing'], _('إغلاق الفترة'))
            if rec.period_role == 'reading':
                rec._validate_period_closing_reconciliation()
            old_s = rec.state
            rec.write({
                'state': 'closed',
                'closed_at': fields.Datetime.now(),
            })
            rec._log_state_transition(old_s, 'closed', _("إغلاق الفترة بعد استكمال المطابقة"))

    def action_reconcile_payment(self):
        """مطابقة السداد (للسجلات التاريخية period_role='payment')."""
        for rec in self:
            if rec.period_role == 'reading':
                # للسجلات الموحّدة: نفوّض إلى action_reconcile_collection
                return rec.action_reconcile_collection()
            rec._validate_state_transition(['closing'], _('مطابقة التحصيل التاريخي'))
            old_s = rec.state
            rec.write({'state': 'reconciled'})
            rec._log_state_transition(old_s, 'reconciled', _("إكمال مطابقة المقبوضات والتحصيل"))

    def action_lock_period(self):
        """إقفال تاريخي: يُقفل الدورة بالكامل بما فيها القراءة والتحصيل."""
        for rec in self:
            rec._validate_state_transition(['closed', 'reconciled'], _('إقفال تاريخي'))
            old_s = rec.state
            rec.write({
                'state': 'locked',
                'locked_at': fields.Datetime.now(),
                'reading_state': 'locked',
                'collection_state': 'locked',
            })
            rec._log_state_transition(old_s, 'locked', _("إقفال تاريخي نائي للدورة"))

    @api.constrains('period_role', 'state')
    def _check_role_state_consistency(self):
        # السجلات الموحّدة (reading) تقبل أي حالة مدعومة
        reading_states = {'planned', 'open', 'closing', 'closed', 'reconciled', 'locked'}
        payment_states = {'planned', 'open', 'closing', 'reconciled', 'locked'}
        for rec in self:
            if rec.period_role == 'reading' and rec.state not in reading_states:
                raise ValidationError(_("الحالة '%s' غير مسموحة لدورة قراءة.") % rec.state)
            elif rec.period_role == 'payment' and rec.state not in payment_states:
                raise ValidationError(_("الحالة '%s' غير مسموحة لفترة تحصيل تاريخية.") % rec.state)

    def action_reopen_period(self, reason="إعادة فتح استثنائي"):
        """إعادة فتح الدورة بالكامل (state). يسجل في سجل التدقيق."""
        for rec in self:
            if rec.state == 'locked':
                raise ValidationError(_("لا يمكن إعادة فتح دورة مقفلة تاريخياً (locked)."))
            rec._validate_state_transition(['closed', 'reconciled', 'closing'], _('إعادة فتح'))
            old_s = rec.state
            rec.write({'state': 'open'})
            rec._log_state_transition(old_s, 'open', reason or _("إعادة فتح الدورة بحسب طلب المستخدم"))


class DateRangeLog(models.Model):
    _name = 'date.range.log'
    _description = 'سجل تدقيق وتغييرات فترات الفوترة'
    _order = 'timestamp desc, id desc'

    period_id = fields.Many2one('date.range', string="الفترة", required=True, ondelete='cascade', index=True)
    old_state = fields.Char(string="الحالة السابقة")
    new_state = fields.Char(string="الحالة الجديدة")
    user_id = fields.Many2one('res.users', string="المستخدم", default=lambda self: self.env.user)
    timestamp = fields.Datetime(string="التاريخ والوقت", default=fields.Datetime.now)
    reason = fields.Text(string="السبب / البيان")
    action_type = fields.Char(string="نوع الإجراء")
    changed_fields = fields.Char(string="الحقول المعدلة")
    old_values = fields.Text(string="القيم السابقة")
    new_values = fields.Text(string="القيم الجديدة")
    workflow_id = fields.Char(string="مرجع مسار العمل (Workflow Ref)")
    workflow_run_id = fields.Char(string="مرجع تشغيل مسار العمل (Workflow Run Ref)")
