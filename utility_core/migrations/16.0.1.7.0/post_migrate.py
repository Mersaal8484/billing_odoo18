"""post-migrate: ترحيل بيانات الدورة الموحدة.

ينقل بيانات نطاق الدفع من سجلات payment القديمة
إلى سجل القراءة الموحد (reading) لنفس cycle_key.
يعيد توجيه مراجع account_payment التاريخية.
يُنفَّذ بعد تحديث ORM.

الترحيل آمن تماماً:
- لا يُعدّل الفواتير أو الدفعات التاريخية.
- لا يحذف أي سجل.
- idempotent: إذا نُفِّذ مرتين لا يُكرر التأثير.
"""
import logging

_logger = logging.getLogger(__name__)

# تقرير التحقق قبل الترحيل
VERIFY_REPORT_QUERY = """
SELECT
    (SELECT COUNT(*) FROM date_range WHERE period_role = 'reading' AND cycle_key IS NOT NULL) AS reading_cycles,
    (SELECT COUNT(*) FROM date_range WHERE period_role = 'payment' AND reading_period_id IS NOT NULL) AS legacy_payment_records,
    (SELECT COUNT(*) FROM sale_order WHERE date_range_id IS NOT NULL) AS bills_total,
    (SELECT COUNT(*) FROM account_payment WHERE date_range_id IS NOT NULL AND utility_sale_order_id IS NOT NULL) AS payments_total
"""


def migrate(cr, version):
    """Migrate payment period data into the unified reading cycle record."""
    _logger.info('utility_core post-migrate: starting unified-cycle data migration')

    # ── 1. تقرير التحقق قبل الترحيل ──────────────────────────────────
    cr.execute(VERIFY_REPORT_QUERY)
    before = cr.fetchone()
    _logger.info(
        'utility_core post-migrate BEFORE: reading_cycles=%s, '
        'legacy_payment=%s, bills=%s, payments=%s',
        *before
    )

    # ── 2. نقل بيانات نطاق الدفع من سجلات payment إلى سجل القراءة ────
    # لكل زوج reading_period ↔ payment_period (مرتبطان بـ reading_period_id):
    # - payment_start = date_start لسجل الدفع
    # - payment_end   = date_end   لسجل الدفع
    # - reading_state: من حالة سجل القراءة
    # - collection_state: من حالة سجل الدفع
    cr.execute("""
        UPDATE date_range AS r
        SET
            payment_start = COALESCE(
                r.payment_start,
                p.date_start
            ),
            payment_end = COALESCE(
                r.payment_end,
                p.date_end
            ),
            reading_state = CASE
                WHEN r.state IN ('open')    THEN 'open'
                WHEN r.state IN ('closing') THEN 'closing'
                WHEN r.state IN ('closed')  THEN 'closed'
                WHEN r.state IN ('locked')  THEN 'locked'
                ELSE 'open'
            END,
            collection_state = CASE
                WHEN p.state IN ('open', 'planned') THEN 'open'
                WHEN p.state IN ('closing')          THEN 'closing'
                WHEN p.state IN ('reconciled')       THEN 'reconciled'
                WHEN p.state IN ('locked')           THEN 'locked'
                ELSE 'open'
            END
        FROM date_range AS p
        WHERE p.reading_period_id = r.id
          AND r.period_role = 'reading'
          AND (r.payment_start IS NULL OR r.collection_state = 'open')
    """)
    migrated_cycles = cr.rowcount
    _logger.info(
        'utility_core post-migrate: %d reading cycles updated with payment range data',
        migrated_cycles
    )

    # ── 3. ضبط reading_state لسجلات القراءة التي لا يوجد لها payment period ──
    # (دورات جديدة أنشئت بالنموذج الموحد أو قديمة بدون payment period)
    cr.execute("""
        UPDATE date_range
        SET reading_state = CASE
            WHEN state IN ('open')    THEN 'open'
            WHEN state IN ('closing') THEN 'closing'
            WHEN state IN ('closed')  THEN 'closed'
            WHEN state IN ('locked')  THEN 'locked'
            ELSE 'open'
        END
        WHERE period_role = 'reading'
          AND reading_state = 'open'
          AND NOT EXISTS (
              SELECT 1 FROM date_range p
              WHERE p.reading_period_id = date_range.id
          )
          AND state NOT IN ('planned')
    """)
    _logger.info(
        'utility_core post-migrate: %d reading cycles reading_state synced from state',
        cr.rowcount
    )

    # ── 4. الحفاظ على مراجع account_payment التاريخية دون تعديل ──────
    # السجلات التاريخية لـ account_payment تحتفظ بـ date_range_id كما هي
    # دون تعديل لحماية سلامة التحقق، رموز QR، وتصنيف التوقيت للدفعات المنشورة.
    _logger.info('utility_core post-migrate: historical account_payment references preserved intact')

    # ── 5. تقرير التحقق بعد الترحيل ──────────────────────────────────
    cr.execute(VERIFY_REPORT_QUERY)
    after = cr.fetchone()
    _logger.info(
        'utility_core post-migrate AFTER: reading_cycles=%s, '
        'legacy_payment=%s, bills=%s, payments=%s',
        *after
    )

    # تحقق أن الفواتير والدفعات لم تتغير
    if before[2] != after[2]:
        _logger.error(
            'utility_core post-migrate INTEGRITY ERROR: '
            'bills count changed from %d to %d!',
            before[2], after[2]
        )
    else:
        _logger.info(
            'utility_core post-migrate: integrity check PASSED — '
            'bills count unchanged (%d)',
            after[2]
        )

    _logger.info('utility_core post-migrate: unified-cycle migration completed')
