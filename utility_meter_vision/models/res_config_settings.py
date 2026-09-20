from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    meter_vision_service_url = fields.Char(
        string='رابط خدمة تحليل صور العدادات',
        config_parameter='utility_meter_vision.service_url',
        help='مثال: http://meter-vision-service:8000',
    )
    meter_vision_service_token = fields.Char(
        string='رمز خدمة تحليل الصور', config_parameter='utility_meter_vision.service_token',
    )
    meter_vision_timeout = fields.Integer(
        string='مهلة الخدمة بالثواني', default=30,
        config_parameter='utility_meter_vision.timeout',
    )
