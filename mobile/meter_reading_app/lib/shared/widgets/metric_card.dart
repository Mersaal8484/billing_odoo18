import 'package:flutter/material.dart';

enum MetricCardLayout {
  labelValue,
  iconValueLabel,
  iconLabelValue,
  iconLeading,
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.label,
    required this.value,
    this.icon,
    this.layout = MetricCardLayout.labelValue,
    this.card = true,
    this.padding = const EdgeInsets.all(12),
    this.iconColor,
    this.crossAxisAlignment = CrossAxisAlignment.center,
    this.mainAxisAlignment = MainAxisAlignment.start,
    this.iconSpacing = 8,
    this.labelValueSpacing = 4,
    this.labelStyle,
    this.valueStyle,
    this.labelTextAlign,
    this.valueTextAlign,
  });

  final String label;
  final String value;
  final IconData? icon;
  final MetricCardLayout layout;
  final bool card;
  final EdgeInsetsGeometry padding;
  final Color? iconColor;
  final CrossAxisAlignment crossAxisAlignment;
  final MainAxisAlignment mainAxisAlignment;
  final double iconSpacing;
  final double labelValueSpacing;
  final TextStyle? labelStyle;
  final TextStyle? valueStyle;
  final TextAlign? labelTextAlign;
  final TextAlign? valueTextAlign;

  @override
  Widget build(BuildContext context) {
    final child = Padding(
      padding: padding,
      child: _buildContent(context),
    );

    if (!card) return child;
    return Card(child: child);
  }

  Widget _buildContent(BuildContext context) {
    return switch (layout) {
      MetricCardLayout.iconLeading => Row(
          children: [
            _buildIcon(context),
            SizedBox(width: iconSpacing),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildLabel(context),
                  _buildValue(context),
                ],
              ),
            ),
          ],
        ),
      MetricCardLayout.iconValueLabel => Column(
          crossAxisAlignment: crossAxisAlignment,
          mainAxisAlignment: mainAxisAlignment,
          children: [
            _buildIcon(context),
            SizedBox(height: iconSpacing),
            _buildValue(context),
            _buildLabel(context),
          ],
        ),
      MetricCardLayout.iconLabelValue => Column(
          crossAxisAlignment: crossAxisAlignment,
          mainAxisAlignment: mainAxisAlignment,
          children: [
            _buildIcon(context),
            SizedBox(height: iconSpacing),
            _buildLabel(context),
            SizedBox(height: labelValueSpacing),
            _buildValue(context),
          ],
        ),
      MetricCardLayout.labelValue => Column(
          crossAxisAlignment: crossAxisAlignment,
          mainAxisAlignment: mainAxisAlignment,
          children: [
            _buildLabel(context),
            SizedBox(height: labelValueSpacing),
            _buildValue(context),
          ],
        ),
    };
  }

  Widget _buildIcon(BuildContext context) {
    return Icon(icon, color: iconColor ?? Theme.of(context).colorScheme.primary);
  }

  Widget _buildLabel(BuildContext context) {
    return Text(
      label,
      style: labelStyle ?? Theme.of(context).textTheme.bodySmall,
      textAlign: labelTextAlign,
    );
  }

  Widget _buildValue(BuildContext context) {
    return Text(
      value,
      style: valueStyle,
      textAlign: valueTextAlign,
    );
  }
}
