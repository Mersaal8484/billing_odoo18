import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../app/providers.dart';

class QrScannerScreen extends ConsumerStatefulWidget {
  final bool isReaderMode;

  const QrScannerScreen({super.key, this.isReaderMode = false});

  @override
  ConsumerState<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends ConsumerState<QrScannerScreen>
    with WidgetsBindingObserver {
  // MobileScanner 5.x يدير الصلاحيات داخلياً — لا نحتاج permission_handler
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
    facing: CameraFacing.back,
    torchEnabled: false,
  );

  final _manualController = TextEditingController();
  bool _resolving = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // يجب بدء الكاميرا عند التهيئة وإلا ستنهار مكتبة mobile_scanner في الأندرويد
    _controller.start();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    switch (state) {
      case AppLifecycleState.resumed:
        _controller.start();
        break;
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
        _controller.stop();
        break;
      default:
        break;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _manualController.dispose();
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    if (_resolving) return;
    final payload = capture.barcodes
        .map((barcode) => barcode.rawValue?.trim())
        .whereType<String>()
        .firstWhere((value) => value.isNotEmpty, orElse: () => '');
    if (payload.isEmpty) return;
    await _resolvePayload(payload);
  }

  Future<void> _resolvePayload(String payload) async {
    if (_resolving) return;
    setState(() {
      _resolving = true;
      _message = null;
    });

    try {
      await _controller.stop();

      if (widget.isReaderMode) {
        final repository = ref.read(assignmentRepositoryProvider);
        await repository.syncOpenPeriodAssignments();
        final assignment = await repository.resolveQr(payload);
        if (!mounted) return;
        if (assignment == null) {
          setState(() {
            _resolving = false;
            _message =
                'هذا الرمز غير موجود ضمن مهام فترة القراءة المفتوحة أو خارج مسارك.';
          });
          await _controller.start();
          return;
        }
        context.go('/customers/${assignment.id}');
        return;
      }

      final repository = ref.read(collectionRepositoryProvider);
      await repository.syncPeriodInvoices();
      final account = await repository.resolveQr(payload);
      if (!mounted) return;
      if (account == null) {
        setState(() {
          _resolving = false;
          _message =
              'هذا الرمز غير موجود ضمن فواتير فترة التحصيل المفتوحة أو خارج مسارك.';
        });
        await _controller.start();
        return;
      }
      context.go('/collector/accounts/${account.id}');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _resolving = false;
        _message = 'تعذر قراءة الرمز: $error';
      });
      await _controller.start();
    }
  }

  Future<void> _submitManualCode() async {
    final payload = _manualController.text.trim();
    if (payload.isEmpty) {
      setState(() => _message = 'أدخل رقم المشترك أو الحساب أو العداد.');
      return;
    }
    await _resolvePayload(payload);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('مسح QR'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: 'تشغيل/إيقاف الفلاش',
            onPressed: () => _controller.toggleTorch(),
            icon: const Icon(Icons.flash_on_rounded),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Expanded(
                child: Center(
                  child: AspectRatio(
                    aspectRatio: 1,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(24),
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          MobileScanner(
                            controller: _controller,
                            onDetect: _handleBarcode,
                            errorBuilder: (context, error) {
                              // نعرض نص الخطأ الفعلي لمساعدة التشخيص
                              return ColoredBox(
                                color: Colors.black,
                                child: Center(
                                  child: Column(
                                    mainAxisAlignment:
                                        MainAxisAlignment.center,
                                    children: [
                                      const Icon(Icons.camera_alt_outlined,
                                          color: Colors.white54, size: 48),
                                      const SizedBox(height: 12),
                                      const Text(
                                        'تعذر تشغيل الكاميرا',
                                        style:
                                            TextStyle(color: Colors.white),
                                      ),
                                      const SizedBox(height: 6),
                                      Padding(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 16),
                                        child: Text(
                                          error.errorDetails?.message ??
                                              error.errorCode.name,
                                          style: const TextStyle(
                                              color: Colors.white54,
                                              fontSize: 11),
                                          textAlign: TextAlign.center,
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      ElevatedButton(
                                        onPressed: () =>
                                            _controller.start(),
                                        child: const Text('إعادة المحاولة'),
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
                          // إطار الماسح
                          DecoratedBox(
                            decoration: BoxDecoration(
                              border:
                                  Border.all(color: Colors.white, width: 3),
                              borderRadius: BorderRadius.circular(24),
                            ),
                          ),
                          if (_resolving)
                            const ColoredBox(
                              color: Colors.black45,
                              child: Center(
                                child: CircularProgressIndicator(
                                    color: Colors.white),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              if (_message != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.18),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _message!,
                    style: const TextStyle(color: Colors.white),
                    textAlign: TextAlign.center,
                  ),
                ),
              TextField(
                controller: _manualController,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _submitManualCode(),
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'إدخال يدوي للرمز أو رقم المشترك',
                  hintStyle: const TextStyle(color: Colors.white70),
                  prefixIcon: const Icon(Icons.keyboard_alt_outlined,
                      color: Colors.white70),
                  suffixIcon: IconButton(
                    onPressed: _resolving ? null : _submitManualCode,
                    icon: const Icon(Icons.search_rounded),
                    color: Colors.white,
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderSide: const BorderSide(color: Colors.white54),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderSide: const BorderSide(color: Colors.white),
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              TextButton.icon(
                onPressed: () => context
                    .go(widget.isReaderMode ? '/customers' : '/collector'),
                icon: const Icon(Icons.arrow_back_rounded),
                label: const Text('رجوع للإدخال اليدوي'),
                style: TextButton.styleFrom(foregroundColor: Colors.white),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
