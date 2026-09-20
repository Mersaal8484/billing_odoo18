# Detection annotations

التنسيق المقترح YOLO: ملف نصي لكل صورة، كل سطر:

```text
class_id x_center y_center width height
```

جميع القيم normalized بين 0 و1. خزن أسماء الفئات وإصدارها في
`configs/annotation-spec.json`.
