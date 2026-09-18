# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo import fields


@tagged('post_install', '-at_install', 'utility_release', 'utility_billing')
class TestBlockDiscountBusinessLogic(TransactionCase):
    """
    اختبارات منطق الأعمال المتقدمة للخصومات بالشرائح (Block Discounts):
    - توزيع كميات الخصم على عدة شرائح خصم تصاعدية
    - توثيق شرائح الخصم في بنود أمر البيع بأسعار سالبة ولقطة التسعير (Pricing Snapshot)
    - ربط الخصم بالجهة الراعية والداعمة (Sponsor)
    - قيد التحقق الصارم: رفض القالب إذا كانت شرائح الخصم لا تغطي كامل كمية الخصم المطلوبة
    - حالة انعدام الخصم (0 units) وعدم توليد بنود خصم فارغة
    - ثبات شرائح الخصم التاريخية عند وجود إصدارات (Version Snapshot)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.Partner = cls.env['res.partner']
        cls.Customer = cls.env['utility.customer']
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Template = cls.env['utility.contract.template']
        cls.Block = cls.env['utility.contract.template.block']
        cls.Line = cls.env['utility.contract.template.line']
        cls.Formula = cls.env['utility.formula']
        cls.Product = cls.env['product.product']

        # فئة ومشترك
        cls.category = cls.Category.create({
            'name': 'فئة الدعم الاجتماعي لاختبار الخصومات',
            'code': 'CAT-DISC-TEST',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'مشترك مدعوم',
            'code': 'SUB-DISC-TEST',
            'category_id': cls.category.id,
        })

        # جهة راعية / داعمة (Sponsor)
        cls.sponsor_partner = cls.Partner.create({
            'name': 'صندوق دعم الطاقة الكهربائية (Sponsor)',
        })

        # منتج الطاقة ومنتج الخصم
        cls.kwh_product = cls.env.ref('utility_core.utility_product_kwh', raise_if_not_found=False)
        if not cls.kwh_product:
            cls.kwh_product = cls.Product.create({
                'name': 'طاقة كهربائية',
                'type': 'service',
            })

        cls.discount_product = cls.Product.create({
            'name': 'بند دعم واستهلاك مخصوم',
            'type': 'service',
        })

        # معادلة الخصم: تخصيص أول 120 كيلوواط للخصم (أو الاستهلاك إذا كان أقل)
        cls.formula_120 = cls.Formula.create({
            'name': 'معادلة دعم أول 120 كيلوواط',
            'code': 'result = min(consumption, 120.0)',
        })

        # معادلة خصم لا تغطيها الشرائح (150 كيلوواط)
        cls.formula_150 = cls.Formula.create({
            'name': 'معادلة دعم 150 كيلوواط',
            'code': 'result = min(consumption, 150.0)',
        })

        # قالب عقد بشرائح تسعير وشرائح خصم
        # سعر الطاقة: 100 ريال / كيلوواط
        # شرائح الخصم:
        # شريحة خصم 1: من 0 إلى 50 kWh بخصم 40 ريال / kWh
        # شريحة خصم 2: من 50 إلى 120 kWh بخصم 25 ريال / kWh
        # شريحة خصم 3: من 120 إلى ما لا نهاية (0) بخصم 10 ريال / kWh
        cls.template = cls.Template.create({
            'name': 'قالب التعرفة المدعومة بشرائح الخصم',
            'code': 'TPL-DISC-BLOCKS-01',
            'pricing_mode': 'flat',
            'price_per_kwh': 100.0,
            'service_charge': 400.0,
            'sponsor_id': cls.sponsor_partner.id,
            'discount_formula_id': cls.formula_120.id,
            'subscriber_category_ids': [(6, 0, cls.category.ids)],
            'subscriber_ids': [(6, 0, cls.subscriber.ids)],
            'scope': 'global',
        })

        # إضافة بند الخصم في خطوط القالب
        cls.discount_line = cls.Line.create({
            'template_id': cls.template.id,
            'name': 'دعم الكهرباء الاجتماعي',
            'meter_line_type': 'discount',
            'product_id': cls.discount_product.id,
            'sponsor_id': cls.sponsor_partner.id,
            'qty_formula_id': cls.formula_120.id,
            'sequence': 10,
        })

        # إنشاء شرائح الخصم على القالب (is_discount = True)
        cls.d_block_1 = cls.Block.create({
            'template_id': cls.template.id,
            'name': 'شريحة الخصم الأولى',
            'sequence': 10,
            'from_kwh': 0.0,
            'to_kwh': 50.0,
            'price_per_kwh': 40.0,
            'is_discount': True,
        })
        cls.d_block_2 = cls.Block.create({
            'template_id': cls.template.id,
            'name': 'شريحة الخصم الثانية',
            'sequence': 20,
            'from_kwh': 50.0,
            'to_kwh': 120.0,
            'price_per_kwh': 25.0,
            'is_discount': True,
        })
        cls.d_block_3 = cls.Block.create({
            'template_id': cls.template.id,
            'name': 'شريحة الخصم المفتوحة',
            'sequence': 30,
            'from_kwh': 120.0,
            'to_kwh': 0.0,  # ما لا نهاية
            'price_per_kwh': 10.0,
            'is_discount': True,
        })

        # شريك وحساب العميل
        cls.partner = cls.Partner.create({'name': 'المواطن المستفيد من الدعم'})
        cls.customer = cls.Customer.create({
            'customer_number': 'CUST-DISC-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
            'contract_template_id': cls.template.id,
        })

        # دورة شهرية
        range_type = cls.env['date.range.type'].search([], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({'name': 'دورة خصومات', 'work_type': 'readings'})
        cls.period = cls.env['date.range'].create({
            'name': 'فترة الخصومات 2026-09',
            'type_id': range_type.id,
            'date_start': '2026-09-01',
            'date_end': '2026-09-30',
            'state': 'open',
            'period_role': 'reading',
            'company_id': cls.company.id,
        })

    def test_01_progressive_block_discount_distribution(self):
        """
        اختبار توزيع الخصم على عدة شرائح خصم تصاعدية:
        - الاستهلاك: 200 kWh.
        - طاقة الاستهلاك: 200 * 100 = 20,000 ريال.
        - كمية الخصم المحسوبة بالمعادلة: min(200, 120) = 120 kWh.
        - توزيع وحدات الخصم (120 kWh):
          * شريحة الخصم 1 (0 إلى 50): 50 kWh @ -40 = -2,000 ريال.
          * شريحة الخصم 2 (50 إلى 120): 70 kWh @ -25 = -1,750 ريال.
          * إجمالي الخصم = -3,750 ريال.
        - رسوم الخدمة: 400 ريال.
        - إجمالي الفاتورة الصافي: 20,000 - 3,750 + 400 = 16,650 ريال.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 200.0,
            'contract_template_id': self.template.id,
        })
        order._calculate_amounts()

        # 1. التحقق من مبالغ الفاتورة
        self.assertEqual(order.amount_energy, 20000.0)
        self.assertEqual(order.amount_discount, -3750.0)
        self.assertEqual(order.amount_service, 400.0)
        self.assertEqual(order.amount_total, 16650.0)

        # 2. التحقق من بنود أمر البيع (Sale Order Lines) الخاصة بالخصم
        discount_lines = order.order_line.filtered(lambda l: l.meter_line_type == 'discount')
        self.assertEqual(len(discount_lines), 2, 'يجب إنشاء بندين للخصم يمثلان الشريحتين المستهلكتين.')

        line1 = discount_lines.filtered(lambda l: '0 إلى 50' in l.name)
        line2 = discount_lines.filtered(lambda l: '50 إلى 120' in l.name)

        self.assertTrue(line1)
        self.assertEqual(line1.product_uom_qty, 50.0)
        self.assertEqual(line1.price_unit, -40.0)
        self.assertEqual(line1.price_subtotal, -2000.0)
        self.assertEqual(line1.sponsor_id.id, self.sponsor_partner.id)

        self.assertTrue(line2)
        self.assertEqual(line2.product_uom_qty, 70.0)
        self.assertEqual(line2.price_unit, -25.0)
        self.assertEqual(line2.price_subtotal, -1750.0)
        self.assertEqual(line2.sponsor_id.id, self.sponsor_partner.id)

        # 3. التحقق من لقطة التسعير (Pricing Snapshot)
        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)
        self.assertEqual(snapshot.amount_discount, -3750.0)

        # شرائح الخصم في اللقطة
        d_blocks_in_snapshot = snapshot.block_ids.filtered(lambda b: b.is_discount)
        self.assertEqual(len(d_blocks_in_snapshot), 2)
        self.assertEqual(sum(d_blocks_in_snapshot.mapped('quantity')), 120.0)
        self.assertEqual(sum(d_blocks_in_snapshot.mapped('amount')), -3750.0)

    def test_02_partial_discount_block_fill(self):
        """
        اختبار استهلاك يقع بالكامل داخل أول شريحة خصم:
        - الاستهلاك: 30 kWh.
        - كمية الخصم: 30 kWh.
        - الشريحة الأولى تمتد حتى 50 kWh، لذلك تأخذ كامل الـ 30 kWh.
        - مبلغ الخصم: 30 * -40 = -1,200 ريال.
        - يجب توليد بند خصم واحد فقط، وعدم استخدام الشريحة الثانية.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 30.0,
            'contract_template_id': self.template.id,
        })
        order._calculate_amounts()

        self.assertEqual(order.amount_energy, 3000.0)
        self.assertEqual(order.amount_discount, -1200.0)

        discount_lines = order.order_line.filtered(lambda l: l.meter_line_type == 'discount')
        self.assertEqual(len(discount_lines), 1)
        self.assertEqual(discount_lines[0].product_uom_qty, 30.0)
        self.assertEqual(discount_lines[0].price_unit, -40.0)

        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        d_blocks = snapshot.block_ids.filtered(lambda b: b.is_discount)
        self.assertEqual(len(d_blocks), 1)
        self.assertEqual(d_blocks[0].quantity, 30.0)

    def test_03_uncovered_discount_units_raises_validation_error(self):
        """
        قيد التحقق: إذا كانت وحدات الخصم المطلوبة بالمعادلة تتجاوز نطاق تغطية شرائح الخصم،
        يجب أن يرفع النظام ValidationError صريحاً يوضح عدم اكتمال التغطية.
        """
        # قالب بشرائح خصم تنتهي عند 80 فقط (بدون شريحة مفتوحة)
        template_limited = self.Template.create({
            'name': 'قالب خصم محدود النطاق',
            'code': 'TPL-DISC-LIMITED',
            'pricing_mode': 'flat',
            'price_per_kwh': 100.0,
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'subscriber_ids': [(6, 0, self.subscriber.ids)],
            'scope': 'global',
        })
        self.Block.create({
            'template_id': template_limited.id,
            'name': 'شريحة وحيدة محدودة',
            'from_kwh': 0.0,
            'to_kwh': 80.0,
            'price_per_kwh': 30.0,
            'is_discount': True,
        })
        self.Line.create({
            'template_id': template_limited.id,
            'name': 'بند خصم 150 كيلوواط',
            'meter_line_type': 'discount',
            'product_id': self.discount_product.id,
            'qty_formula_id': self.formula_150.id,  # يطلب 150 kWh بينما الشرائح تغطي 80 فقط
        })

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 200.0,
            'contract_template_id': template_limited.id,
        })

        with self.assertRaises(ValidationError) as cm:
            order._calculate_amounts()
        self.assertIn('لا يغطي كامل وحدات الخصم بالشرائح', str(cm.exception))

    def test_04_zero_discount_units_generates_no_discount_lines(self):
        """
        الاستهلاك الصفري أو انعدام كمية الخصم:
        - عند استهلاك 0، كمية الخصم تكون 0.
        - لا يجب توليد أي بنود خصم أو شرائح في لقطة التسعير.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 0.0,
            'contract_template_id': self.template.id,
        })
        order._calculate_amounts()

        self.assertEqual(order.amount_discount, 0.0)
        discount_lines = order.order_line.filtered(lambda l: l.meter_line_type == 'discount')
        self.assertEqual(len(discount_lines), 0)

        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        d_blocks = snapshot.block_ids.filtered(lambda b: b.is_discount)
        self.assertEqual(len(d_blocks), 0)
