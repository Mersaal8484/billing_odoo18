# meter-vision-service

خدمة مستقلة لتحليل صور عدادات الكهرباء، مصممة لتُستدعى من إضافة `utility_meter_vision`.

## التشغيل

```text
python -m venv .venv
\.venv\Scripts\pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

اختبار الصحة: `GET /healthz`

التحليل: `POST /v1/inference` مع `request_id` و`image_base64`. عند ضبط
`METER_VISION_API_TOKEN` يجب إرسال `Authorization: Bearer ...`.

النسخة الحالية baseline: تتحقق من سلامة الصورة وحجمها وجودتها، وتستخدم
Tesseract اختيارياً إن تم تثبيت `requirements-ocr.txt` ومحرك Tesseract الأصلي.
غياب OCR أو تعدد المرشحين يعيد `needs_review` ولا يعتمد القراءة آلياً.

## التطوير اللاحق

يُستبدل `_ocr` تدريجياً بمرحلة كشف شاشة العداد، تصنيف النوع، نموذج قراءة مخصص
لكل عائلة عدادات، ثم قواعد تحقق مع القراءة السابقة. لا تُحفظ الصور داخل الخدمة؛
تظل الصور ونتائج التحليل في Odoo/التخزين المعتمد.
