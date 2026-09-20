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

When `display_bbox` is supplied, the service first normalizes the crop, removes
small noise, improves contrast/sharpness, and evaluates multiple OCR variants.
For slanted screens, `display_quad` can be supplied with eight coordinates in
the order TL, TR, BR, BL; the service rectifies the screen before OCR. Send
either `display_bbox` or `display_quad`, never both.

Digital LCD screens use the local seven-segment recognizer in
`app/seven_segment_ocr.py`. Mechanical roller displays must send
`meter_type_hint: "mechanical_roller"` or `"mechanical_round"`, which selects
the multi-variant roller OCR ensemble in `app/roller_ocr.py`. The ensemble
returns a reading only when independent variants agree; otherwise the image
stays `needs_review`.

`expected_digits` can be supplied when the meter family has a fixed register
width. It is a validation constraint, not a license to pad or invent digits.

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

## Local CRNN bootstrap training

The optional trainer is intentionally separate from runtime inference:

```text
python train_crnn.py ..\meter-vision-data\processed\ocr-single-review\manifest.jsonl --reading-format integer_6 --output ..\meter-vision-data\processed\ocr-single-review\reading_ocr.pt --epochs 40
```

The checkpoint is experimental until the held-out exact-reading accuracy gate
is met. A failed gate must not be copied into `models/` or enabled in the API.
Each checkpoint is trained for a single register layout; mixing integer and
decimal displays, or different digit counts, produces unreliable OCR.
