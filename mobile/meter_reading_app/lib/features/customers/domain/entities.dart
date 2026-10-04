// Domain-level entities. These are what the UI and business logic work
// with; they are intentionally decoupled from both the Drift row classes
// (local storage detail) and any future Odoo JSON shape (remote detail).
// Mapping between the three lives only in the data layer.

class Customer {
  final int remoteId;
  final String customerNumber;
  final String accountNumber;
  final String name;
  final String? mobile;
  final String? address;
  final String? regionName;
  final String? areaName;
  final DateTime? lastReadingDate;
  final double? lastReadingValue;

  const Customer({
    required this.remoteId,
    required this.customerNumber,
    required this.accountNumber,
    required this.name,
    this.mobile,
    this.address,
    this.regionName,
    this.areaName,
    this.lastReadingDate,
    this.lastReadingValue,
  });
}

enum MeterPaymentType { postpaid, prepaid, manual }

class Meter {
  final int remoteId;
  final String meterNumber;
  final String? serialNumber;
  final int customerRemoteId;
  final MeterPaymentType paymentType;
  final String? meterType;
  final String connectionStatus;
  final bool isCouplingMeter;

  const Meter({
    required this.remoteId,
    required this.meterNumber,
    this.serialNumber,
    required this.customerRemoteId,
    required this.paymentType,
    this.meterType,
    this.connectionStatus = 'connected',
    this.isCouplingMeter = false,
  });
}

/// A single unit of field work: one meter, for one customer, for the
/// active billing period, with its current local status.
enum AssignmentStatus {
  pending,
  pendingDecision,
  read,
  rejected,
  escalated,
  skipped
}

class ReadingAssignment {
  final String id;
  final Meter meter;
  final Customer customer;

  /// Identity of the reading period downloaded with this assignment.
  final int? periodId;
  final AssignmentStatus status;
  final DateTime scheduledAt;
  final double averageConsumption;

  const ReadingAssignment({
    required this.id,
    required this.meter,
    required this.customer,
    this.periodId,
    required this.status,
    required this.scheduledAt,
    required this.averageConsumption,
  });
}
