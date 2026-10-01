{
    'name': 'Utility Meter Vision',
    'version': '18.0.0.0.0',
    'category': 'Utility ERP',
    'summary': '[قيد التطوير - غير مفعّل] طلبات تحليل صور العدادات بالذكاء الاصطناعي',
    'description': (
        'وحدة مستقبلية لتحليل صور العدادات عبر OCR/Computer Vision. '
        'هذه الوحدة قيد التطوير وليست جزءاً من إصدار V1 الحالي. '
        'لا يجب تثبيتها في بيئات الإنتاج. '
        'سيتم تفعيلها في مرحلة V2 بعد اكتمال التطوير والاختبار.'
    ),
    'author': 'Utility ERP Platform',
    'license': 'LGPL-3',
    'depends': ['utility_core'],
    'data': [
        'security/utility_meter_vision_security.xml',
        'security/ir.model.access.csv',
        'data/utility_meter_vision_data.xml',
        'views/utility_meter_vision_views.xml',
        'views/utility_meter_vision_menu.xml',
        'views/res_config_settings_views.xml',
    ],
    # -------------------------------------------------------------------
    # FUTURE MODULE — NOT PART OF V1
    # هذه الوحدة قيد التطوير ولن تُثبَّت في بيئة الإنتاج الحالية.
    # سيتم تفعيلها في V2 بعد اكتمال التطوير والاختبار والتحقق.
    # -------------------------------------------------------------------
    'installable': False,
    'application': False,
    'auto_install': False,
    'development_status': 'Alpha',
}

