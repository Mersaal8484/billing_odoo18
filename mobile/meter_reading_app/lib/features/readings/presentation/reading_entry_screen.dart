import 'dart:io';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image/image.dart' as img;
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../../../app/providers.dart';
import '../../../core/network/odoo_api_client.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../customers/data/mock_assignment_repository.dart';
import '../../customers/domain/entities.dart';
import '../domain/reading.dart';

class ReadingEntryScreen extends ConsumerStatefulWidget {
  final String assignmentId;
  const ReadingEntryScreen({super.key, required this.assignmentId});

  @override
  ConsumerState<ReadingEntryScreen> createState() => _ReadingEntryScreenState();
}

class _ReadingEntryScreenState extends ConsumerState<ReadingEntryScreen> {
  final _formKey = GlobalKey<FormState>();
  final _readingCtrl = TextEditingController();
  final _remarksCtrl = TextEditingController();

  ReadingAssignment? _assignment;
  _MeterInfo? _meterInfo;
  bool _loadingMeter = true;
  String? _loadError;
  File? _capturedImage;
  bool _savingReading = false;

  @override
  void initState() {
    super.initState();
    _loadAssignmentAndMeter();
  }

  @override
  void dispose() {
    _readingCtrl.dispose();
    _remarksCtrl.dispose();
    super.dispose();
  }

  // ── تحميل بيانات التكليف والعداد ─────────────────────────────────────────

  Future<void> _loadAssignmentAndMeter() async {
    setState(() {
      _loadingMeter = true;
      _loadError = null;
    });

    try {
      final repo = ref.read(assignmentRepositoryProvider);

      // استخدام getById أولاً، ثم البحث برقم العداد أو QR
      final assignment =
          await repo.getById(widget.assignmentId) ??
          await repo.lookupByMeterNumber(widget.assignmentId) ??
          await repo.resolveQr(widget.assignmentId);

      if (assignment == null) {
        setState(() => _loadError = 'لم يُعثر على التكليف');
        return;
      }

      _MeterInfo meterInfo;
      try {
        meterInfo = await _fetchMeterInfoFromOdoo(assignment.meter.meterNumber);
      } catch (_) {
        meterInfo = _MeterInfo.offline();
      }

      setState(() {
        _assignment = assignment;
        _meterInfo = meterInfo;
        _loadingMeter = false;
      });

      // ── منع القراءة المكررة ──────────────────────────────────────────────
      if (meterInfo.alreadyReadThisPeriod && !meterInfo.canResubmit && mounted) {
        await showDialog(
          context: context,
          barrierDismissible: false,
          builder: (_) => AlertDialog(
            icon: const Icon(Icons.block, color: Colors.red, size: 40),
            title: const Text('تم أخذ القراءة مسبقاً'),
            content: Text(
              'لقد تم أخذ قراءة هذا العداد (${assignment.meter.meterNumber}) '
              'في الفترة الحالية بالفعل.\n\n'
              'القراءة المسجّلة: ${meterInfo.lastReadingValue} kWh',
            ),
            actions: [
              FilledButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  if (mounted) context.pop();
                },
                child: const Text('العودة'),
              ),
            ],
          ),
        );
      }
    } on OdooSessionExpiredException {
      setState(() => _loadError = 'انتهت الجلسة — سجّل الدخول مجدداً');
    } catch (e) {
      setState(() {
        _loadingMeter = false;
        _meterInfo = _MeterInfo.offline();
      });
    }
  }

  Future<_MeterInfo> _fetchMeterInfoFromOdoo(String meterNumber) async {
    final client = ref.read(odooApiClientProvider);

    // جلب الفترة الحالية
    final periodResult =
        await client.postJson('/api/v1/utility/reading/periods', {});
    final periods = (periodResult['periods'] as List?) ?? [];
    int? currentPeriodId;
    if (periods.isNotEmpty) {
      final current = periods
          .cast<Map<String, dynamic>>()
          .firstWhere((p) => p['is_current'] == true,
              orElse: () => periods.first as Map<String, dynamic>);
      currentPeriodId = current['id'] as int?;
    }

    // جلب آخر قراءة للعداد
    final lookupResult = await client.postJson(
        '/api/v1/utility/reading/meter/lookup', {'meter_number': meterNumber});

    final lastValue =
        (lookupResult['last_reading_value'] as num?)?.toDouble() ?? 0.0;
    final lastDate = lookupResult['last_reading_date'] as String?;
    final avgConsumption =
        (lookupResult['avg_consumption'] as num?)?.toDouble() ?? 0.0;

    // التحقق من القراءة المكررة
    bool alreadyRead = false;
    bool canResubmit = false;
    int? resubmitReadingId;
    String? rejectionReason;
    if (currentPeriodId != null) {
      try {
        final checkResult = await client.postJson(
            '/api/v1/utility/reading/check_period_reading', {
          'meter_code': meterNumber,
          'period_id': currentPeriodId,
        });
        alreadyRead = checkResult['has_reading'] == true;
        canResubmit = checkResult['can_resubmit'] == true;
        resubmitReadingId = checkResult['resubmit_reading_id'] as int?;
        rejectionReason = checkResult['rejection_reason'] as String?;
      } catch (_) {}
    }

    return _MeterInfo(
      lastReadingValue: lastValue,
      lastReadingDate: lastDate,
      avgConsumption: avgConsumption,
      currentPeriodId: currentPeriodId,
      alreadyReadThisPeriod: alreadyRead,
      canResubmit: canResubmit,
      resubmitReadingId: resubmitReadingId,
      rejectionReason: rejectionReason,
    );
  }

  // ── التقاط الصورة + Watermark ─────────────────────────────────────────────

  Future<void> _capturePhotoWithWatermark() async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      _showSnack('الكاميرا غير متاحة');
      return;
    }
    if (!mounted) return;
    final result = await Navigator.of(context).push<File>(
      MaterialPageRoute(builder: (_) => _CameraScreen(camera: cameras.first)),
    );
    if (result == null) return;
    final watermarked = await _addWatermark(result);
    setState(() => _capturedImage = watermarked);
  }

  Future<File> _addWatermark(File imageFile) async {
    final bytes = await imageFile.readAsBytes();
    final original = img.decodeImage(bytes);
    if (original == null) return imageFile;

    final now = DateTime.now();
    // التاريخ بصيغة yyyy-MM-dd — أحمر كبير مثل الصور
    final dateStr = DateFormat('yyyy-MM-dd').format(now);

    // حجم الخط نسبة لعرض الصورة
    final fontSize = (original.width * 0.10).round().clamp(40, 200);

    // رسم ظل أبيض/أسود للوضوح على أي خلفية
    for (final dx in [-2, 0, 2]) {
      for (final dy in [-2, 0, 2]) {
        if (dx == 0 && dy == 0) continue;
        img.drawString(
          original,
          dateStr,
          font: img.arial48,
          x: (original.width * 0.04).round() + dx,
          y: (original.height * 0.60).round() + dy,
          color: img.ColorRgba8(0, 0, 0, 180),
        );
      }
    }

    // النص الأحمر الرئيسي
    img.drawString(
      original,
      dateStr,
      font: img.arial48,
      x: (original.width * 0.04).round(),
      y: (original.height * 0.60).round(),
      color: img.ColorRgba8(220, 30, 30, 255),
    );

    // ── Adaptive compression: must stay ≤ 95 KB to satisfy the 100 KB API limit ──
    const int maxBytes = 95 * 1024; // 95 KB — leaves 5 KB headroom

    // Probe at quality=75 first
    Uint8List compressed = Uint8List.fromList(img.encodeJpg(original, quality: 75));

    if (compressed.lengthInBytes > maxBytes) {
      // Estimate quality needed: newQ ≈ 75 × (maxBytes / probeSize), clamped [30, 70]
      final ratio = maxBytes / compressed.lengthInBytes;
      final estQ = (75 * ratio).clamp(30.0, 70.0).toInt();
      compressed = Uint8List.fromList(img.encodeJpg(original, quality: estQ));

      if (compressed.lengthInBytes > maxBytes) {
        // Still over — shrink to 70% width and try again
        final narrowed = img.copyResize(original, width: (original.width * 0.7).toInt());
        final attempt3 = Uint8List.fromList(img.encodeJpg(narrowed, quality: estQ));
        if (attempt3.lengthInBytes < compressed.lengthInBytes) {
          compressed = attempt3;
        }
      }
    }

    final dir = await getApplicationDocumentsDirectory();
    final path = '${dir.path}/reading_${const Uuid().v4()}.jpg';
    final outFile = File(path);
    await outFile.writeAsBytes(compressed);
    return outFile;
  }


  // ── حفظ القراءة ──────────────────────────────────────────────────────────

  Future<void> _saveReading() async {
    if (!_formKey.currentState!.validate()) return;

    if (_capturedImage == null) {
      _showSnack('يجب تصوير العداد قبل الحفظ');
      return;
    }
    if (_meterInfo?.alreadyReadThisPeriod == true &&
        _meterInfo?.canResubmit != true) {
      _showSnack('تم أخذ هذه القراءة مسبقاً في الفترة الحالية');
      return;
    }

    final readingValue = double.tryParse(_readingCtrl.text.trim()) ?? 0;
    final prevValue = _meterInfo?.lastReadingValue ?? 0;
    if (readingValue < prevValue) {
      _showSnack(
          'القراءة الحالية ($readingValue) أقل من السابقة ($prevValue kWh)!',
          isError: true);
      return;
    }

    setState(() => _savingReading = true);

    try {
      final assignment = _assignment!;

      final reading = MeterReading(
        id: const Uuid().v4(),
        remoteId: _meterInfo?.resubmitReadingId,
        meterRemoteId: assignment.meter.remoteId,
        meterNumber: assignment.meter.meterNumber,
        readingValue: readingValue,
        readingDate: DateTime.now(),
        category: ReadingCategory.customer,
        isEstimated: false,
        remarks: _remarksCtrl.text.trim().isEmpty
            ? null
            : _remarksCtrl.text.trim(),
        imageLocalPath: _capturedImage!.path,
        photoUuid: const Uuid().v4(),
        syncStatus: ReadingSyncStatus.draft,
        // بصمة الفترة المفتوحة الآن — يقارنها SyncEngine بالفترة المفتوحة
        // وقت الرفع لاحقاً، فلا تُلصق قراءة قديمة بفترة جديدة بالخطأ.
        capturedPeriodId: _meterInfo?.currentPeriodId,
      );

      // 1. حفظ محلي
      await ref.read(readingRepositoryProvider).saveDraft(reading);

      // 2. تحديث حالة التكليف → read
      await ref
          .read(assignmentRepositoryProvider)
          .markStatus(assignment.id, AssignmentStatus.read);

      // 3. إضافة لطابور المزامنة
      await ref.read(syncEngineProvider).enqueue(reading);

      if (mounted) {
        _showSnack('تم حفظ القراءة وإضافتها لطابور الرفع ✓');
        await Future.delayed(const Duration(milliseconds: 800));
        context.pop();
      }
    } catch (e) {
      _showSnack('خطأ في الحفظ: $e', isError: true);
    } finally {
      if (mounted) setState(() => _savingReading = false);
    }
  }

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('إدخال القراءة'),
        centerTitle: true,
      ),
      body: _loadingMeter
          ? const Center(child: CircularProgressIndicator())
          : _loadError != null
              ? ErrorState(
                  message: _loadError!, onRetry: _loadAssignmentAndMeter)
              : _buildForm(scheme),
    );
  }

  Widget _buildForm(ColorScheme scheme) {
    final assignment = _assignment!;
    final meterInfo = _meterInfo!;

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // بطاقة المشترك
          Card(
            child: ListTile(
              leading:
                  const CircleAvatar(child: Icon(Icons.person_outline)),
              title: Text(assignment.customer.name,
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: Text(
                'عداد ${assignment.meter.meterNumber} · حساب ${assignment.customer.accountNumber}',
              ),
            ),
          ),
          const SizedBox(height: 12),

          if (meterInfo.canResubmit)
            Card(
              color: scheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Icon(Icons.replay_rounded, color: scheme.onErrorContainer),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        meterInfo.rejectionReason?.isNotEmpty == true
                            ? 'أعاد المراجع هذه القراءة للتصحيح: ${meterInfo.rejectionReason}'
                            : 'أعاد المراجع هذه القراءة للتصحيح. أدخل القراءة والتقط صورة جديدة.',
                        style: TextStyle(color: scheme.onErrorContainer),
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // القراءة السابقة
          Card(
            color: scheme.secondaryContainer.withOpacity(0.4),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Icon(Icons.history, color: scheme.secondary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('القراءة السابقة',
                            style: TextStyle(
                                color: scheme.secondary,
                                fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Text('${meterInfo.lastReadingValue} kWh',
                                style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold)),
                            if (meterInfo.avgConsumption > 0) ...[
                              const SizedBox(width: 12),
                              Text(
                                '· المتوسط ${meterInfo.avgConsumption.toStringAsFixed(0)} kWh',
                                style: TextStyle(
                                    color: scheme.outline, fontSize: 12),
                              ),
                            ],
                          ],
                        ),
                        if (meterInfo.isOffline)
                          Text('⚠ وضع غير متصل',
                              style: TextStyle(
                                  color: scheme.error, fontSize: 11)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // حقل القراءة الحالية
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('القراءة الحالية (kWh)',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _readingCtrl,
                    keyboardType: const TextInputType.numberWithOptions(
                        decimal: true),
                    decoration: InputDecoration(
                      hintText: 'أدخل قراءة العداد',
                      suffixText: 'kWh',
                      border: const OutlineInputBorder(),
                      filled: true,
                      fillColor:
                          scheme.surfaceVariant.withOpacity(0.3),
                    ),
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold),
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'القراءة مطلوبة';
                      final val = double.tryParse(v);
                      if (val == null) return 'رقم غير صحيح';
                      if (val < meterInfo.lastReadingValue) {
                        return 'يجب أن تكون >= ${meterInfo.lastReadingValue} kWh';
                      }
                      return null;
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // تصوير العداد
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('صورة العداد',
                          style:
                              Theme.of(context).textTheme.titleMedium),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: _capturedImage != null
                              ? Colors.green.withOpacity(0.15)
                              : scheme.errorContainer,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          _capturedImage != null ? 'تم ✓' : 'مطلوب',
                          style: TextStyle(
                            fontSize: 11,
                            color: _capturedImage != null
                                ? Colors.green
                                : scheme.error,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (_capturedImage != null) ...[
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.file(_capturedImage!,
                          height: 180,
                          width: double.infinity,
                          fit: BoxFit.cover),
                    ),
                    const SizedBox(height: 8),
                  ],
                  OutlinedButton.icon(
                    onPressed: _capturePhotoWithWatermark,
                    icon: Icon(_capturedImage != null
                        ? Icons.refresh
                        : Icons.camera_alt_outlined),
                    label: Text(_capturedImage != null
                        ? 'إعادة التصوير'
                        : 'تصوير العداد'),
                    style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(44)),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // ملاحظات
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: TextFormField(
                controller: _remarksCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: 'ملاحظات (اختياري)',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
          ),
          const SizedBox(height: 24),

          // زر الحفظ
          FilledButton.icon(
            onPressed:
                (_savingReading ||
                        (meterInfo.alreadyReadThisPeriod &&
                            !meterInfo.canResubmit))
                    ? null
                    : _saveReading,
            icon: _savingReading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.cloud_upload_outlined),
            label: Text(_savingReading
                ? 'جاري الحفظ...'
                : 'حفظ القراءة وإضافتها للرفع'),
            style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52)),
          ),

          if (meterInfo.isOffline)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.cloud_off, size: 14, color: scheme.outline),
                  const SizedBox(width: 4),
                  Text(
                    'وضع غير متصل — تُرفع عند توفر الشبكة',
                    style:
                        TextStyle(fontSize: 11, color: scheme.outline),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor:
          isError ? Theme.of(context).colorScheme.error : null,
    ));
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// شاشة الكاميرا
// ─────────────────────────────────────────────────────────────────────────────

class _CameraScreen extends StatefulWidget {
  final CameraDescription camera;
  const _CameraScreen({required this.camera});

  @override
  State<_CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<_CameraScreen>
    with WidgetsBindingObserver {
  late CameraController _controller;
  late Future<void> _initFuture;
  bool _taking = false;
  double _minZoom = 1.0;
  double _maxZoom = 1.0;
  double _currentZoom = 1.0;
  Offset? _focusPoint;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _controller = CameraController(
      widget.camera,
      ResolutionPreset.high,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );
    _initFuture = _controller.initialize().then((_) async {
      _minZoom = await _controller.getMinZoomLevel();
      _maxZoom = await _controller.getMaxZoomLevel();
      // زوم افتراضي خفيف للتركيز على القراءة
      _currentZoom = (_maxZoom * 0.25).clamp(_minZoom, _maxZoom);
      if (mounted) {
        setState(() {});
        await _controller.setZoomLevel(_currentZoom);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.dispose();
    super.dispose();
  }

  Future<void> _onTapFocus(TapUpDetails details, BoxConstraints constraints) async {
    final offset = Offset(
      details.localPosition.dx / constraints.maxWidth,
      details.localPosition.dy / constraints.maxHeight,
    );
    setState(() => _focusPoint = details.localPosition);
    await _controller.setFocusPoint(offset);
    await _controller.setExposurePoint(offset);
    await Future.delayed(const Duration(milliseconds: 800));
    if (mounted) setState(() => _focusPoint = null);
  }

  Future<void> _shoot() async {
    if (_taking) return;
    setState(() => _taking = true);
    try {
      await _controller.setFocusMode(FocusMode.locked);
      final xfile = await _controller.takePicture();
      if (mounted) Navigator.of(context).pop(File(xfile.path));
    } catch (e) {
      setState(() => _taking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: FutureBuilder<void>(
        future: _initFuture,
        builder: (_, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(
                child: CircularProgressIndicator(color: Colors.white));
          }
          final size = MediaQuery.of(context).size;

          return Stack(
            children: [
              // ── معاينة الكاميرا ──────────────────────────────────────
              SizedBox.expand(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    return GestureDetector(
                      onTapUp: (d) => _onTapFocus(d, constraints),
                      child: CameraPreview(_controller),
                    );
                  },
                ),
              ),

              // ── تعتيم خارج الإطار ────────────────────────────────────
              _FrameOverlay(
                screenSize: size,
              ),

              // ── نقطة التركيز ─────────────────────────────────────────
              if (_focusPoint != null)
                Positioned(
                  left: _focusPoint!.dx - 24,
                  top: _focusPoint!.dy - 24,
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.yellow, width: 2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),

              // ── AppBar ────────────────────────────────────────────────
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    child: Row(
                      children: [
                        IconButton(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.close,
                              color: Colors.white, size: 28),
                        ),
                        const Spacer(),
                        const Text('تصوير العداد',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.w600)),
                        const Spacer(),
                        const SizedBox(width: 48), // مساحة متوازية للرجوع
                      ],
                    ),
                  ),
                ),
              ),

              // ── توجيه نصي ────────────────────────────────────────────
              Positioned(
                top: MediaQuery.of(context).padding.top + 64,
                left: 16,
                right: 16,
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Text(
                      'ضع أرقام العداد داخل الإطار بوضوح',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w500),
                    ),
                  ),
                ),
              ),

              // ── شريط الزوم ───────────────────────────────────────────
              if (_maxZoom > _minZoom + 0.5)
                Positioned(
                  bottom: 120,
                  left: 40,
                  right: 40,
                  child: Row(
                    children: [
                      const Icon(Icons.zoom_out,
                          color: Colors.white70, size: 20),
                      Expanded(
                        child: Slider(
                          value: _currentZoom,
                          min: _minZoom,
                          max: _maxZoom.clamp(_minZoom, _minZoom + 5),
                          divisions: 20,
                          activeColor: Colors.white,
                          inactiveColor: Colors.white30,
                          onChanged: (v) async {
                            setState(() => _currentZoom = v);
                            await _controller.setZoomLevel(v);
                          },
                        ),
                      ),
                      const Icon(Icons.zoom_in,
                          color: Colors.white70, size: 20),
                    ],
                  ),
                ),

              // ── زر التقاط ────────────────────────────────────────────
              Positioned(
                bottom: 32,
                left: 0,
                right: 0,
                child: Center(
                  child: GestureDetector(
                    onTap: _shoot,
                    child: Container(
                      width: 76,
                      height: 76,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white,
                        border: Border.all(
                            color: Colors.white70, width: 4),
                        boxShadow: const [
                          BoxShadow(
                              color: Colors.black45,
                              blurRadius: 8,
                              spreadRadius: 2)
                        ],
                      ),
                      child: _taking
                          ? const Padding(
                              padding: EdgeInsets.all(18),
                              child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.black))
                          : const Icon(Icons.camera_alt,
                              size: 36, color: Colors.black),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ── طبقة التعتيم مع الإطار ────────────────────────────────────────────────────
class _FrameOverlay extends StatelessWidget {
  final Size screenSize;
  const _FrameOverlay({required this.screenSize});

  @override
  Widget build(BuildContext context) {
    final w = screenSize.width;
    final h = screenSize.height;

    // أبعاد الإطار
    final frameW = w * 0.85;
    final frameH = h * 0.25; // يأخذ مساحة كافية للعداد والأرقام
    final frameTop = (h - frameH) / 2;
    final frameLeft = (w - frameW) / 2;

    return CustomPaint(
      size: Size(w, h),
      painter: _OverlayPainter(
        frameRect: Rect.fromLTWH(frameLeft, frameTop, frameW, frameH),
      ),
    );
  }
}

class _OverlayPainter extends CustomPainter {
  final Rect frameRect;
  _OverlayPainter({required this.frameRect});

  @override
  void paint(Canvas canvas, Size size) {
    final shadow = Paint()..color = Colors.black.withOpacity(0.55);
    final fullRect = Rect.fromLTWH(0, 0, size.width, size.height);

    // تعتيم خارج الإطار
    final path = Path()
      ..addRect(fullRect)
      ..addRRect(RRect.fromRectAndRadius(frameRect, const Radius.circular(8)))
      ..fillType = PathFillType.evenOdd;
    canvas.drawPath(path, shadow);

    // إطار مضيء
    final borderPaint = Paint()
      ..color = Colors.white70
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    canvas.drawRRect(
      RRect.fromRectAndRadius(frameRect, const Radius.circular(8)),
      borderPaint,
    );

    // زوايا إطار مميزة
    final cornerPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    const cLen = 22.0;
    final r = frameRect;

    // زاوية يسار أعلى
    canvas.drawLine(r.topLeft, r.topLeft + const Offset(cLen, 0), cornerPaint);
    canvas.drawLine(r.topLeft, r.topLeft + const Offset(0, cLen), cornerPaint);
    // زاوية يمين أعلى
    canvas.drawLine(r.topRight, r.topRight + const Offset(-cLen, 0), cornerPaint);
    canvas.drawLine(r.topRight, r.topRight + const Offset(0, cLen), cornerPaint);
    // زاوية يسار أسفل
    canvas.drawLine(r.bottomLeft, r.bottomLeft + const Offset(cLen, 0), cornerPaint);
    canvas.drawLine(r.bottomLeft, r.bottomLeft + const Offset(0, -cLen), cornerPaint);
    // زاوية يمين أسفل
    canvas.drawLine(r.bottomRight, r.bottomRight + const Offset(-cLen, 0), cornerPaint);
    canvas.drawLine(r.bottomRight, r.bottomRight + const Offset(0, -cLen), cornerPaint);
  }

  @override
  bool shouldRepaint(_OverlayPainter old) => old.frameRect != frameRect;
}


// ─────────────────────────────────────────────────────────────────────────────
// خطأ
// ─────────────────────────────────────────────────────────────────────────────

class _MeterInfo {
  final double lastReadingValue;
  final String? lastReadingDate;
  final double avgConsumption;
  final int? currentPeriodId;
  final bool alreadyReadThisPeriod;
  final bool canResubmit;
  final int? resubmitReadingId;
  final String? rejectionReason;
  final bool isOffline;

  const _MeterInfo({
    required this.lastReadingValue,
    this.lastReadingDate,
    this.avgConsumption = 0,
    this.currentPeriodId,
    this.alreadyReadThisPeriod = false,
    this.canResubmit = false,
    this.resubmitReadingId,
    this.rejectionReason,
    this.isOffline = false,
  });

  factory _MeterInfo.offline() =>
      const _MeterInfo(lastReadingValue: 0, isOffline: true);
}
