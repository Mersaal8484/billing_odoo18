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

تتضمن الخدمة الآن مراحل الجودة، وكشف العداد، وتصنيف النوع، وOCR، وقواعد
التحقق. الأوزان المطلوبة معرفة في `models/model_manifest.json`. الأوزان غير
الموجودة تظهر `not_ready` عبر `GET /v1/models`، وتبقى النتيجة `needs_review`.
النسخة الحالية baseline تتحقق من سلامة الصورة وحجمها وجودتها، وتستخدم Tesseract
اختيارياً إن تم تثبيت `requirements-ocr.txt` ومحرك Tesseract الأصلي.

## التطوير اللاحق

تُستبدل مراحل الكشف والتصنيف و`_ocr` تدريجياً بالأوزان المدربة لكل عائلة عدادات،
ثم تُفعل قواعد التحقق مع القراءة السابقة. لا تُحفظ الصور داخل الخدمة؛
تظل الصور ونتائج التحليل في Odoo/التخزين المعتمد.
