# Dataset scripts

الأدوات الحالية:

```text
python scripts/create_collection_manifest.py D:\datameter --output reports/datameter-collection-2026-09-20.json
python scripts/validate_annotations.py annotations/ocr/annotation.json --root D:\datameter
python scripts/prepare_ocr_dataset.py annotations/ocr/annotation.json --root D:\datameter --output processed/ocr-v1
```

ينشئ الأمر الأول فهرساً محلياً لكل الصور، ويضع الصور المصغرة بعلامة
`thumbnail`، ولا يعتمد أي قراءة أو مربع تلقائياً.

الأداة الأولى تمنع الصناديق خارج الصورة والقراءات غير المكتملة والصور الصغيرة
من المرور. الأداة الثانية لا تأخذ إلا `double_review` أو `gold`، وتقص شاشة
القراءة، وتقسم حسب `group_id` إلى train/val/test حتى لا تتسرب صور نفس العداد
بين المجموعات. لا تعدل الصور الأصلية.
