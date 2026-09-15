import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../app/providers.dart';
import '../../../app/theme/app_theme.dart';
import '../../../core/image/image_processing_service.dart';

/// Captures a meter photo, then runs it through [ImageProcessingService]
/// before handing a *local* file path back to the caller.
class PhotoCaptureScreen extends ConsumerStatefulWidget {
  const PhotoCaptureScreen({super.key});
  @override
  ConsumerState<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends ConsumerState<PhotoCaptureScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  Future<void>? _initFuture;
  String? _capturedPath;
  int? _processedSizeBytes;
  bool _processing = false;
  bool _readabilityWarning = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initFuture = _initCamera();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final CameraController? cameraController = _controller;
    if (cameraController == null || !cameraController.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      _disposeCamera();
    } else if (state == AppLifecycleState.resumed && _capturedPath == null) {
      _initFuture = _initCamera();
    }
  }

  void _disposeCamera() {
    _controller?.dispose();
    _controller = null;
  }

  Future<void> _initCamera() async {
    // Dispose any existing controller first to avoid conflicts
    _disposeCamera();

    try {
      final status = await Permission.camera.request();
      if (status.isDenied || status.isPermanentlyDenied) {
        if (mounted) {
          setState(
              () => _error = 'صلاحية الكاميرا مطلوبة لالتقاط قراءة العداد.');
        }
        return;
      }

      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        if (mounted) {
          setState(() => _error = 'لا توجد كاميرا متاحة على هذا الجهاز.');
        }
        return;
      }

      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      // ResolutionPreset.medium is more stable across devices than high
      final newController = CameraController(
        back,
        ResolutionPreset.medium,
        enableAudio: false,
      );
      await newController.initialize();
      // setFocusMode/setExposureMode may not be supported on all devices
      try { await newController.setFocusMode(FocusMode.auto); } catch (_) {}
      try { await newController.setExposureMode(ExposureMode.auto); } catch (_) {}
      // The guide is centred, so focus there initially. This affects focus
      // only; the complete photo is always retained as inspection evidence.
      try {
        await newController.setFocusPoint(const Offset(0.5, 0.5));
        await newController.setExposurePoint(const Offset(0.5, 0.5));
      } catch (_) {}

      if (!mounted) {
        newController.dispose();
        return;
      }
      setState(() {
        _controller = newController;
        _error = null;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'تعذر تشغيل الكاميرا: $e');
      }
    }
  }

  Future<void> _capture() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    if (_processing) return;

    try {
      // Show spinner IMMEDIATELY — setState + ensure frame renders before any
      // heavy work, so the user sees feedback even if processing is very fast.
      setState(() => _processing = true);
      // Yield to the frame scheduler so the spinner actually paints before
      // we hand off to compute().
      await Future<void>.delayed(Duration.zero);

      // 1. Take the picture
      final xfile = await controller.takePicture();

      // 2. Process the complete camera image in a separate Isolate.
      // The on-screen frame is an alignment/focus guide only: it must never
      // crop inspection evidence such as the meter seal, enclosure or damage.
      final processor = ref.read(imageProcessingServiceProvider);
      final result = await processor.process(File(xfile.path));

      // 4. Delete the raw temp file from the camera plugin's cache dir
      try { await File(xfile.path).delete(); } catch (_) {}

      // 4. Save the processed JPEG to the app's documents directory
      final dir = await getApplicationDocumentsDirectory();
      final readingsDir = Directory(p.join(dir.path, 'readings'));
      await readingsDir.create(recursive: true);
      final destPath = p.join(
          readingsDir.path, '${DateTime.now().microsecondsSinceEpoch}.jpg');
      await File(destPath).writeAsBytes(result.bytes);

      if (!mounted) return;

      // 5. Switch to review screen (CameraPreview is no longer rendered)
      setState(() {
        _capturedPath = destPath;
        _processedSizeBytes = result.sizeBytes;
        _readabilityWarning = result.belowReadabilityFloor;
        _processing = false;
      });

    } catch (e) {
      if (mounted) {
        setState(() {
          _processing = false;
          _error = 'فشل التقاط الصورة: $e';
        });
      }
    }
  }

  Future<void> _disposeControllerSafely(CameraController c) async {
    try {
      await c.dispose();
    } catch (_) {}
    if (_controller == c) _controller = null;
  }

  Future<void> _focusOnMeter() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;

    // The guide is intentionally centred. Tapping it re-runs autofocus and
    // auto-exposure on the meter without changing the captured image area.
    try {
      await controller.setFocusPoint(const Offset(0.5, 0.5));
      await controller.setExposurePoint(const Offset(0.5, 0.5));
    } catch (_) {
      // Some device cameras do not expose focus/exposure point controls.
    }
  }

  void _retake() {
    setState(() {
      _capturedPath = null;
      _processedSizeBytes = null;
      _readabilityWarning = false;
      _error = null;
    });
    _initFuture = _initCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: const Text('تصوير العداد'),
      ),
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline,
                        color: Colors.redAccent, size: 48),
                    const SizedBox(height: 16),
                    Text(_error!,
                        style: const TextStyle(color: Colors.white),
                        textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () {
                        setState(() => _error = null);
                        _initFuture = _initCamera();
                      },
                      child: const Text('إعادة المحاولة'),
                    )
                  ],
                ),
              ),
            )
          : _capturedPath != null
              ? _buildReview()
              : _buildLiveCamera(),
    );
  }

  Widget _buildLiveCamera() {
    return FutureBuilder(
      future: _initFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(
              child: CircularProgressIndicator(color: Colors.white));
        }

        final controller = _controller;
        if (controller == null || !controller.value.isInitialized) {
          return const Center(
              child: CircularProgressIndicator(color: Colors.white));
        }

        final size = MediaQuery.of(context).size;
        final camRatio = controller.value.aspectRatio;
        final screenRatio = size.width / size.height;
        // Scale to fill the screen without letterboxing
        final scale = camRatio < screenRatio
            ? screenRatio / camRatio
            : camRatio / screenRatio;

        return Stack(
          fit: StackFit.expand,
          children: [
            // Camera preview filling the full screen
            ClipRect(
              child: Transform.scale(
                scale: scale,
                child: Center(
                  child: AspectRatio(
                    aspectRatio: camRatio,
                    child: CameraPreview(controller),
                  ),
                ),
              ),
            ),
            // A visual guide only. The whole camera image is saved so a
            // reviewer can inspect the meter body, seal and surrounding state.
            Center(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: _focusOnMeter,
                child: Container(
                  width: size.width * 0.86,
                  height: (size.height * 0.42).clamp(230.0, 390.0).toDouble(),
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.white70, width: 2),
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ),
            // Hint text
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.5),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'ضع أرقام العداد داخل الإطار',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white, fontSize: 13),
                ),
              ),
            ),
            // Shutter button
            Positioned(
              bottom: 40,
              left: 0,
              right: 0,
              child: Center(
                child: _processing
                    ? const Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircularProgressIndicator(color: Colors.white),
                          SizedBox(height: 12),
                          Text('جاري معالجة الصورة...',
                              style: TextStyle(color: Colors.white70)),
                        ],
                      )
                    : GestureDetector(
                        onTap: _capture,
                        child: Container(
                          width: 76,
                          height: 76,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.white.withOpacity(0.15),
                            border: Border.all(color: Colors.white, width: 4),
                          ),
                          child: const Icon(Icons.camera_alt,
                              color: Colors.white, size: 32),
                        ),
                      ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildReview() {
    return Column(
      children: [
        Expanded(
          child: Container(
            color: Colors.black,
            child: Image.file(
              File(_capturedPath!),
              fit: BoxFit.contain,
              errorBuilder: (_, e, __) => const Center(
                child: Text('تعذر عرض الصورة',
                    style: TextStyle(color: Colors.white)),
              ),
            ),
          ),
        ),
        if (_readabilityWarning)
          Container(
            width: double.infinity,
            color: StatusColors.error.withOpacity(0.20),
            padding: const EdgeInsets.all(12),
            child: const Text(
              'تحذير: قد تكون الصورة غير واضحة. يُفضّل إعادة التصوير.',
              style: TextStyle(color: Colors.white),
              textAlign: TextAlign.center,
            ),
          ),
        Container(
          color: Colors.black,
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          child: Row(
            children: [
              Text(
                  '${((_processedSizeBytes ?? 0) / 1024).toStringAsFixed(1)} KB',
                  style: const TextStyle(color: Colors.white70)),
              const Spacer(),
              SizedBox(
                width: 130,
                height: 44,
                child: OutlinedButton(
                  onPressed: _retake,
                  style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white54),
                      // إلغاء صريح لأي وراثة محتملة من الثيم العام بدل
                      // الاعتماد فقط على SizedBox الخارجي.
                      minimumSize: const Size(80, 40),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap),
                  child: const Text('إعادة التصوير'),
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 130,
                height: 44,
                child: FilledButton(
                  onPressed: () => Navigator.of(context).pop(_capturedPath),
                  style: FilledButton.styleFrom(
                      // إلغاء صريح لـ minimumSize: Size.fromHeight(56) الموروث
                      // من app_theme.dart (عرض لانهائي) — لا نعتمد فقط على
                      // SizedBox الخارجي لتفادي هذا الخلل مرة أخرى.
                      minimumSize: const Size(80, 40),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap),
                  child: const Text('استخدام الصورة'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
