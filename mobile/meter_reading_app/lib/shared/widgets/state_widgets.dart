import 'package:flutter/material.dart';
import '../../app/theme/app_theme.dart';

class LoadingState extends StatelessWidget {
  final String? message;
  const LoadingState({super.key, this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          if (message != null) ...[
            const SizedBox(height: 16),
            Text(message!, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ],
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;
  const EmptyState(
      {super.key,
      required this.icon,
      required this.title,
      this.subtitle,
      this.action});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 16),
            Text(title,
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
            if (subtitle != null) ...[
              const SizedBox(height: 8),
              Text(subtitle!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(color: Theme.of(context).colorScheme.outline)),
            ],
            if (action != null) ...[const SizedBox(height: 20), action!],
          ],
        ),
      ),
    );
  }
}

class ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const ErrorState({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline,
                size: 56, color: StatusColors.error),
            const SizedBox(height: 16),
            Text(message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge),
            if (onRetry != null) ...[
              const SizedBox(height: 20),
              FilledButton.tonal(
                  onPressed: onRetry, child: const Text('إعادة المحاولة')),
            ],
          ],
        ),
      ),
    );
  }
}

/// Persistent, non-intrusive banner communicating that offline work is
/// completely normal — never an error state — with a manual sync affordance.
class OfflineBanner extends StatelessWidget {
  final bool offline;
  final int pendingCount;
  final VoidCallback onSyncNow;
  const OfflineBanner(
      {super.key,
      required this.offline,
      required this.pendingCount,
      required this.onSyncNow});

  @override
  Widget build(BuildContext context) {
    if (!offline && pendingCount == 0) return const SizedBox.shrink();
    final color = offline ? StatusColors.offline : StatusColors.pending;
    final text = offline
        ? 'وضع عدم الاتصال — سيتم الرفع تلقائياً عند توفر الشبكة'
        : '$pendingCount عنصر بانتظار المزامنة';
    return Material(
      color: color.withValues(alpha: 0.12),
      child: InkWell(
        onTap: offline ? null : onSyncNow,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            children: [
              Icon(offline ? Icons.cloud_off : Icons.sync,
                  size: 18, color: color),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(text,
                      style: TextStyle(
                          color: color,
                          fontWeight: FontWeight.w600,
                          fontSize: 13))),
              if (!offline)
                Text('مزامنة الآن',
                    style: TextStyle(
                        color: color,
                        fontSize: 13,
                        fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}

class SyncStatusChip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData icon;
  final bool showIcon;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final double iconSize;
  final double spacing;
  final double fontSize;
  final FontWeight fontWeight;
  final double backgroundOpacity;

  const SyncStatusChip({
    super.key,
    required this.label,
    required this.color,
    required this.icon,
    this.showIcon = true,
    this.padding = const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    this.borderRadius = 20,
    this.iconSize = 14,
    this.spacing = 4,
    this.fontSize = 12,
    this.fontWeight = FontWeight.w700,
    this.backgroundOpacity = 0.12,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color.withValues(alpha: backgroundOpacity),
        borderRadius: BorderRadius.circular(borderRadius),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showIcon) ...[
            Icon(icon, size: iconSize, color: color),
            SizedBox(width: spacing),
          ],
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: fontSize,
              fontWeight: fontWeight,
            ),
          ),
        ],
      ),
    );
  }
}

class StatusVisual {
  final String label;
  final IconData icon;
  final Color color;

  const StatusVisual(this.label, this.icon, this.color);
}
