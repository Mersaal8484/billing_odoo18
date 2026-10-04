import '../domain/entities.dart';

abstract class AssignmentRepository {
  Stream<List<ReadingAssignment>> watchAssignments(
      {String? query, AssignmentStatus? filter});
  Future<ReadingAssignmentSyncResult> syncOpenPeriodAssignments();
  Future<ReadingAssignment?> getById(String id);
  Future<ReadingAssignment?> lookupByMeterNumber(String meterNumber);
  Future<ReadingAssignment?> resolveQr(String payload);
  Future<void> markStatus(String assignmentId, AssignmentStatus status);
  void dispose();
}

class ReadingAssignmentSyncResult {
  final bool success;
  final bool hasOpenPeriod;
  final String? periodName;
  final int count;
  final String? message;

  const ReadingAssignmentSyncResult({
    required this.success,
    required this.hasOpenPeriod,
    required this.count,
    this.periodName,
    this.message,
  });
}
