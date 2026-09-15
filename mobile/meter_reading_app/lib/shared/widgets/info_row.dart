import 'package:flutter/material.dart';

class InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final EdgeInsetsGeometry padding;
  final double? labelFontSize;
  final FontWeight valueFontWeight;
  final Color? valueColor;
  final double? valueFontSize;

  const InfoRow({
    super.key,
    required this.label,
    required this.value,
    this.padding = EdgeInsets.zero,
    this.labelFontSize,
    this.valueFontWeight = FontWeight.normal,
    this.valueColor,
    this.valueFontSize,
  });

  @override
  Widget build(BuildContext context) {
    final row = Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            color: Theme.of(context).colorScheme.outline,
            fontSize: labelFontSize,
          ),
        ),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.end,
            style: TextStyle(
              fontWeight: valueFontWeight,
              color: valueColor,
              fontSize: valueFontSize,
            ),
          ),
        ),
      ],
    );

    if (padding == EdgeInsets.zero) {
      return row;
    }

    return Padding(
      padding: padding,
      child: row,
    );
  }
}
