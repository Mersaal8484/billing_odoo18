# -*- coding: utf-8 -*-
"""
Definitive fix for utility_security.xml mojibake.
Writes the corrected file directly (confirmed Arabic text from context).
"""

content = """\
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="0">
        <!-- Category -->
        <record id="module_category_utility_erp" model="ir.module.category">
            <field name="name">نظام إدارة الكهرباء</field>
            <field name="description">صلاحيات نظام إدارة الكهرباء</field>
            <field name="sequence">10</field>
        </record>

        <!-- Read Only -->
        <record id="group_utility_readonly" model="res.groups">
            <field name="name">للقراءة فقط</field>
            <field name="category_id" ref="module_category_utility_erp"/>
        </record>

        <!-- Cashier -->
        <record id="group_utility_cashier" model="res.groups">
            <field name="name">أمين صندوق</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_readonly'))]"/>
        </record>

        <!-- Field Collector -->
        <record id="group_utility_collector" model="res.groups">
            <field name="name">متحصل ميداني</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_readonly'))]"/>
        </record>

        <!-- Technician -->
        <record id="group_utility_technician" model="res.groups">
            <field name="name">فني عمليات</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_readonly'))]"/>
        </record>

        <!-- Field Inspector -->
        <record id="group_utility_field_inspector" model="res.groups">
            <field name="name">مفتش ميداني</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_technician'))]"/>
        </record>

        <!-- Supervisor -->
        <record id="group_utility_supervisor" model="res.groups">
            <field name="name">مشرف</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_cashier')), (4, ref('group_utility_collector')), (4, ref('group_utility_technician'))]"/>
        </record>

        <!-- Billing Manager -->
        <record id="group_utility_billing_manager" model="res.groups">
            <field name="name">مدير الفوترة</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_supervisor'))]"/>
        </record>

        <!-- Revenue Manager -->
        <record id="group_utility_revenue_manager" model="res.groups">
            <field name="name">مدير الإيرادات</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_billing_manager'))]"/>
        </record>

        <!-- Auditor -->
        <record id="group_utility_auditor" model="res.groups">
            <field name="name">مراجع / مدقق</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_readonly'))]"/>
        </record>

        <!-- Admin Group -->
        <record id="group_utility_admin" model="res.groups">
            <field name="name">مدير النظام</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_revenue_manager')), (4, ref('group_utility_auditor')), (4, ref('group_utility_field_inspector'))]"/>
            <field name="users" eval="[(4, ref('base.user_admin')), (4, ref('base.user_root'))]"/>
        </record>

        <!-- Make Odoo System Administrators automatically members of Utility Admin -->
        <record id="base.group_system" model="res.groups">
            <field name="implied_ids" eval="[(4, ref('group_utility_admin'))]"/>
        </record>
        <record id="base.group_erp_manager" model="res.groups">
            <field name="implied_ids" eval="[(4, ref('group_utility_admin'))]"/>
        </record>

        <!-- Meter Reader -->
        <record id="group_utility_meter_reader" model="res.groups">
            <field name="name">قارئ عدادات</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_readonly'))]"/>
        </record>

        <!-- Route-based Record Rules (Global AND Intersection) -->
        <record id="utility_customer_route_rule" model="ir.rule">
            <field name="name">Customer Route Access Rule</field>
            <field name="model_id" ref="utility_core.model_utility_customer"/>
            <field name="domain_force">[(1, '=', 1)] if (user._is_global_utility_scope() or user.has_group('utility_core.group_utility_admin') or user.has_group('utility_core.group_utility_billing_manager') or user.has_group('utility_core.group_utility_revenue_manager') or user.has_group('utility_core.group_utility_supervisor') or user.has_group('utility_core.group_utility_auditor') or not (user.has_group('utility_core.group_utility_collector') or user.has_group('utility_core.group_utility_meter_reader') or user.has_group('utility_core.group_utility_technician') or user.has_group('utility_core.group_utility_field_inspector'))) else ([('route_id', 'in', user.assigned_route_ids.ids)] if user.assigned_route_ids else [('id', '=', False)])</field>
            <field name="global" eval="True"/>
        </record>

        <record id="utility_reading_route_rule" model="ir.rule">
            <field name="name">Reading Route Access Rule</field>
            <field name="model_id" ref="utility_core.model_utility_reading"/>
            <field name="domain_force">[(1, '=', 1)] if (user._is_global_utility_scope() or user.has_group('utility_core.group_utility_admin') or user.has_group('utility_core.group_utility_billing_manager') or user.has_group('utility_core.group_utility_revenue_manager') or user.has_group('utility_core.group_utility_supervisor') or user.has_group('utility_core.group_utility_auditor') or not (user.has_group('utility_core.group_utility_collector') or user.has_group('utility_core.group_utility_meter_reader') or user.has_group('utility_core.group_utility_technician') or user.has_group('utility_core.group_utility_field_inspector'))) else ([('customer_id.route_id', 'in', user.assigned_route_ids.ids)] if user.assigned_route_ids else [('id', '=', False)])</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_reading_company_rule" model="ir.rule">
            <field name="name">Reading Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_reading"/>
            <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_customer_company_rule" model="ir.rule">
            <field name="name">Customer Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_customer"/>
            <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <!-- Auditor Geographic Scope: customers are default-deny outside assigned regions. -->
        <record id="utility_customer_auditor_region_rule" model="ir.rule">
            <field name="name">Customer Auditor Geographic Region Rule</field>
            <field name="model_id" ref="utility_core.model_utility_customer"/>
            <field name="domain_force">[(1, '=', 1)] if user.has_group('utility_core.group_utility_admin') else ([('region_id', 'in', user.assigned_region_ids.ids)] if user.assigned_region_ids else [('id', '=', False)])</field>
            <field name="groups" eval="[(4, ref('group_utility_auditor'))]"/>
            <field name="perm_read" eval="True"/>
            <field name="perm_write" eval="False"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_unlink" eval="False"/>
        </record>
        <record id="utility_meter_company_rule" model="ir.rule">
            <field name="name">Meter Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_meter"/>
            <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_route_company_rule" model="ir.rule">
            <field name="name">Route Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_route"/>
            <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_integration_provider_company_rule" model="ir.rule">
            <field name="name">Integration Provider Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_integration_provider"/>
            <field name="domain_force">[('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_integration_log_company_rule" model="ir.rule">
            <field name="name">Integration Log Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_integration_log"/>
            <field name="domain_force">[('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_meter_log_company_rule" model="ir.rule">
            <field name="name">Meter Log Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_meter_log"/>
            <field name="domain_force">[('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>
        <record id="utility_meter_replacement_company_rule" model="ir.rule">
            <field name="name">Meter Replacement Multi-Company Rule</field>
            <field name="model_id" ref="utility_core.model_utility_meter_replacement"/>
            <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
            <field name="global" eval="True"/>
        </record>

        <record id="utility_customer_org_scope_rule" model="ir.rule">
            <field name="name">Customer Unified Organizational Scope Rule</field>
            <field name="model_id" ref="utility_core.model_utility_customer"/>
            <field name="domain_force">[(1, '=', 1)] if user._is_global_utility_scope() else (['|', ('area_id', 'in', user._get_effective_branch_ids()), ('region_id', 'in', user._get_effective_region_ids())] if (user._get_effective_branch_ids() or user._get_effective_region_ids()) else [('id', '=', False)])</field>
            <field name="global" eval="True"/>
        </record>

        <record id="utility_reading_org_scope_rule" model="ir.rule">
            <field name="name">Reading Unified Organizational Scope Rule</field>
            <field name="model_id" ref="utility_core.model_utility_reading"/>
            <field name="domain_force">[(1, '=', 1)] if user._is_global_utility_scope() else (['|', ('account_id.area_id', 'in', user._get_effective_branch_ids()), ('account_id.region_id', 'in', user._get_effective_region_ids())] if (user._get_effective_branch_ids() or user._get_effective_region_ids()) else [('id', '=', False)])</field>
            <field name="global" eval="True"/>
        </record>

        <record id="utility_meter_org_scope_rule" model="ir.rule">
            <field name="name">Meter Unified Organizational Scope Rule</field>
            <field name="model_id" ref="utility_core.model_utility_meter"/>
            <field name="domain_force">[(1, '=', 1)] if user._is_global_utility_scope() else (['|', ('area_id', 'in', user._get_effective_branch_ids()), ('region_id', 'in', user._get_effective_region_ids())] if (user._get_effective_branch_ids() or user._get_effective_region_ids()) else [('id', '=', False)])</field>
            <field name="global" eval="True"/>
        </record>

        <!-- Meter Reader: each reader sees only their own record -->
        <record id="utility_meter_reader_self_rule" model="ir.rule">
            <field name="name">Meter Reader Self Access Rule</field>
            <field name="model_id" ref="utility_core.model_utility_meter_reader"/>
            <field name="domain_force">[(1, '=', 1)] if (user.has_group('utility_core.group_utility_admin') or user.has_group('utility_core.group_utility_supervisor')) else [('user_id', '=', user.id)]</field>
            <field name="global" eval="True"/>
        </record>
    
        <record id="group_utility_meter_reader" model="res.groups">
            <field name="name">قارئ عدادات</field>
            <field name="category_id" ref="module_category_utility_erp"/>
            <field name="implied_ids" eval="[(4, ref('group_utility_readonly'))]"/>
        </record>
    </data>
</odoo>
"""

with open(r'F:\invo-system\utility_core\security\utility_security.xml', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done: file written with correct Arabic text.")
