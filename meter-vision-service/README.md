# meter-vision-service

خدمة مستقلة لتحليل صور عدادات الكهرباء، مصممة لتُستدعى من إضافة `utility_meter_vision`.

## التشغيل

```text
python -m venv .venv
\.venv\Scripts\pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

اختبار الصحة: `GET /healthz`

تشغيل فحص دفعي على مجلد صور دون نقل الصور:

```text
python run_batch.py D:\datameter ..\meter-vision-data\reports\datameter-baseline.json
```

التحليل: `POST /v1/inference` مع `request_id` و`image_base64`. عند ضبط
`METER_VISION_API_TOKEN` يجب إرسال `Authorization: Bearer ...`.

تتضمن الخدمة الآن مراحل الجودة، وكشف العداد، وتصنيف النوع، وOCR، وقواعد
التحقق. الأوزان المطلوبة معرفة في `models/model_manifest.json`. الأوزان غير
الموجودة تظهر `not_ready` عبر `GET /v1/models`، وتبقى النتيجة `needs_review`.
النسخة الحالية baseline تتحقق من سلامة الصورة وحجمها وجودتها، وتستخدم Tesseract
اختيارياً إن تم تثبيت `requirements-ocr.txt` ومحرك Tesseract الأصلي.

## الصور المصغرة الميدانية

إذا وصلت صورة بحجم صغير مثل 250×250، ترفع الخدمة حجمها بطريقة محافظة وتحسن
التباين والحدة، لكنها تضيف `LOW_SOURCE_RESOLUTION_UPSCALED` وتبقيها للمراجعة.
رفع الدقة لا يعيد تفاصيل فقدت من الصورة؛ لذلك يجب على تطبيق الهاتف حفظ وإرسال
الصورة الأصلية وعدم إرسال thumbnail أو صورة معاينة.

الـ thumbnail مفيد للعرض فقط. إذا لم يتوفر الأصل، لا تدخل الصورة مجموعة التدريب
الذهبية ولا تعتمد القراءة آلياً.

## التطوير اللاحق

تُستبدل مراحل الكشف والتصنيف و`_ocr` تدريجياً بالأوزان المدربة لكل عائلة عدادات،
ثم تُفعل قواعد التحقق مع القراءة السابقة. لا تُحفظ الصور داخل الخدمة؛
تظل الصور ونتائج التحليل في Odoo/التخزين المعتمد.
# Specialized digital-display OCR

When `display_bbox` is supplied, the service uses the local seven-segment
recognizer in `app/seven_segment_ocr.py`. It does not run generic OCR over the
whole field photo. `expected_digits` can be supplied when the meter family has
a fixed register width; uncertain patterns are returned as `needs_review`.

Example request fields:

```json
{
  "request_id": "field-001",
  "image_base64": "...",
  "display_bbox": {"x": 345, "y": 235, "w": 425, "h": 115},
  "expected_digits": 8,
  "meter_type_hint": "digital_lcd"
}
```

This is the deterministic bootstrap for the project. It is not a trained
production weight yet; the next stage is to fit meter-family-specific weights
using approved original-resolution crops and double-reviewed readings.
