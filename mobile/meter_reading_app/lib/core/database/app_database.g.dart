// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $CustomersTable extends Customers
    with TableInfo<$CustomersTable, Customer> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CustomersTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _remoteIdMeta =
      const VerificationMeta('remoteId');
  @override
  late final GeneratedColumn<int> remoteId = GeneratedColumn<int>(
      'remote_id', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _accountNumberMeta =
      const VerificationMeta('accountNumber');
  @override
  late final GeneratedColumn<String> accountNumber = GeneratedColumn<String>(
      'account_number', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
      'name', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _addressMeta =
      const VerificationMeta('address');
  @override
  late final GeneratedColumn<String> address = GeneratedColumn<String>(
      'address', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _routeIdMeta =
      const VerificationMeta('routeId');
  @override
  late final GeneratedColumn<int> routeId = GeneratedColumn<int>(
      'route_id', aliasedName, true,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _lastReadingDateMeta =
      const VerificationMeta('lastReadingDate');
  @override
  late final GeneratedColumn<DateTime> lastReadingDate =
      GeneratedColumn<DateTime>('last_reading_date', aliasedName, true,
          type: DriftSqlType.dateTime, requiredDuringInsert: false);
  static const VerificationMeta _lastReadingValueMeta =
      const VerificationMeta('lastReadingValue');
  @override
  late final GeneratedColumn<double> lastReadingValue = GeneratedColumn<double>(
      'last_reading_value', aliasedName, true,
      type: DriftSqlType.double, requiredDuringInsert: false);
  static const VerificationMeta _lastSyncedAtMeta =
      const VerificationMeta('lastSyncedAt');
  @override
  late final GeneratedColumn<DateTime> lastSyncedAt = GeneratedColumn<DateTime>(
      'last_synced_at', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns => [
        remoteId,
        accountNumber,
        name,
        address,
        routeId,
        lastReadingDate,
        lastReadingValue,
        lastSyncedAt
      ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'customers';
  @override
  VerificationContext validateIntegrity(Insertable<Customer> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('remote_id')) {
      context.handle(_remoteIdMeta,
          remoteId.isAcceptableOrUnknown(data['remote_id']!, _remoteIdMeta));
    }
    if (data.containsKey('account_number')) {
      context.handle(
          _accountNumberMeta,
          accountNumber.isAcceptableOrUnknown(
              data['account_number']!, _accountNumberMeta));
    } else if (isInserting) {
      context.missing(_accountNumberMeta);
    }
    if (data.containsKey('name')) {
      context.handle(
          _nameMeta, name.isAcceptableOrUnknown(data['name']!, _nameMeta));
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('address')) {
      context.handle(_addressMeta,
          address.isAcceptableOrUnknown(data['address']!, _addressMeta));
    }
    if (data.containsKey('route_id')) {
      context.handle(_routeIdMeta,
          routeId.isAcceptableOrUnknown(data['route_id']!, _routeIdMeta));
    }
    if (data.containsKey('last_reading_date')) {
      context.handle(
          _lastReadingDateMeta,
          lastReadingDate.isAcceptableOrUnknown(
              data['last_reading_date']!, _lastReadingDateMeta));
    }
    if (data.containsKey('last_reading_value')) {
      context.handle(
          _lastReadingValueMeta,
          lastReadingValue.isAcceptableOrUnknown(
              data['last_reading_value']!, _lastReadingValueMeta));
    }
    if (data.containsKey('last_synced_at')) {
      context.handle(
          _lastSyncedAtMeta,
          lastSyncedAt.isAcceptableOrUnknown(
              data['last_synced_at']!, _lastSyncedAtMeta));
    } else if (isInserting) {
      context.missing(_lastSyncedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {remoteId};
  @override
  Customer map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Customer(
      remoteId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}remote_id'])!,
      accountNumber: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}account_number'])!,
      name: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}name'])!,
      address: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}address']),
      routeId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}route_id']),
      lastReadingDate: attachedDatabase.typeMapping.read(
          DriftSqlType.dateTime, data['${effectivePrefix}last_reading_date']),
      lastReadingValue: attachedDatabase.typeMapping.read(
          DriftSqlType.double, data['${effectivePrefix}last_reading_value']),
      lastSyncedAt: attachedDatabase.typeMapping.read(
          DriftSqlType.dateTime, data['${effectivePrefix}last_synced_at'])!,
    );
  }

  @override
  $CustomersTable createAlias(String alias) {
    return $CustomersTable(attachedDatabase, alias);
  }
}

class Customer extends DataClass implements Insertable<Customer> {
  final int remoteId;
  final String accountNumber;
  final String name;
  final String? address;
  final int? routeId;
  final DateTime? lastReadingDate;
  final double? lastReadingValue;
  final DateTime lastSyncedAt;
  const Customer(
      {required this.remoteId,
      required this.accountNumber,
      required this.name,
      this.address,
      this.routeId,
      this.lastReadingDate,
      this.lastReadingValue,
      required this.lastSyncedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['remote_id'] = Variable<int>(remoteId);
    map['account_number'] = Variable<String>(accountNumber);
    map['name'] = Variable<String>(name);
    if (!nullToAbsent || address != null) {
      map['address'] = Variable<String>(address);
    }
    if (!nullToAbsent || routeId != null) {
      map['route_id'] = Variable<int>(routeId);
    }
    if (!nullToAbsent || lastReadingDate != null) {
      map['last_reading_date'] = Variable<DateTime>(lastReadingDate);
    }
    if (!nullToAbsent || lastReadingValue != null) {
      map['last_reading_value'] = Variable<double>(lastReadingValue);
    }
    map['last_synced_at'] = Variable<DateTime>(lastSyncedAt);
    return map;
  }

  CustomersCompanion toCompanion(bool nullToAbsent) {
    return CustomersCompanion(
      remoteId: Value(remoteId),
      accountNumber: Value(accountNumber),
      name: Value(name),
      address: address == null && nullToAbsent
          ? const Value.absent()
          : Value(address),
      routeId: routeId == null && nullToAbsent
          ? const Value.absent()
          : Value(routeId),
      lastReadingDate: lastReadingDate == null && nullToAbsent
          ? const Value.absent()
          : Value(lastReadingDate),
      lastReadingValue: lastReadingValue == null && nullToAbsent
          ? const Value.absent()
          : Value(lastReadingValue),
      lastSyncedAt: Value(lastSyncedAt),
    );
  }

  factory Customer.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Customer(
      remoteId: serializer.fromJson<int>(json['remoteId']),
      accountNumber: serializer.fromJson<String>(json['accountNumber']),
      name: serializer.fromJson<String>(json['name']),
      address: serializer.fromJson<String?>(json['address']),
      routeId: serializer.fromJson<int?>(json['routeId']),
      lastReadingDate: serializer.fromJson<DateTime?>(json['lastReadingDate']),
      lastReadingValue: serializer.fromJson<double?>(json['lastReadingValue']),
      lastSyncedAt: serializer.fromJson<DateTime>(json['lastSyncedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'remoteId': serializer.toJson<int>(remoteId),
      'accountNumber': serializer.toJson<String>(accountNumber),
      'name': serializer.toJson<String>(name),
      'address': serializer.toJson<String?>(address),
      'routeId': serializer.toJson<int?>(routeId),
      'lastReadingDate': serializer.toJson<DateTime?>(lastReadingDate),
      'lastReadingValue': serializer.toJson<double?>(lastReadingValue),
      'lastSyncedAt': serializer.toJson<DateTime>(lastSyncedAt),
    };
  }

  Customer copyWith(
          {int? remoteId,
          String? accountNumber,
          String? name,
          Value<String?> address = const Value.absent(),
          Value<int?> routeId = const Value.absent(),
          Value<DateTime?> lastReadingDate = const Value.absent(),
          Value<double?> lastReadingValue = const Value.absent(),
          DateTime? lastSyncedAt}) =>
      Customer(
        remoteId: remoteId ?? this.remoteId,
        accountNumber: accountNumber ?? this.accountNumber,
        name: name ?? this.name,
        address: address.present ? address.value : this.address,
        routeId: routeId.present ? routeId.value : this.routeId,
        lastReadingDate: lastReadingDate.present
            ? lastReadingDate.value
            : this.lastReadingDate,
        lastReadingValue: lastReadingValue.present
            ? lastReadingValue.value
            : this.lastReadingValue,
        lastSyncedAt: lastSyncedAt ?? this.lastSyncedAt,
      );
  Customer copyWithCompanion(CustomersCompanion data) {
    return Customer(
      remoteId: data.remoteId.present ? data.remoteId.value : this.remoteId,
      accountNumber: data.accountNumber.present
          ? data.accountNumber.value
          : this.accountNumber,
      name: data.name.present ? data.name.value : this.name,
      address: data.address.present ? data.address.value : this.address,
      routeId: data.routeId.present ? data.routeId.value : this.routeId,
      lastReadingDate: data.lastReadingDate.present
          ? data.lastReadingDate.value
          : this.lastReadingDate,
      lastReadingValue: data.lastReadingValue.present
          ? data.lastReadingValue.value
          : this.lastReadingValue,
      lastSyncedAt: data.lastSyncedAt.present
          ? data.lastSyncedAt.value
          : this.lastSyncedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Customer(')
          ..write('remoteId: $remoteId, ')
          ..write('accountNumber: $accountNumber, ')
          ..write('name: $name, ')
          ..write('address: $address, ')
          ..write('routeId: $routeId, ')
          ..write('lastReadingDate: $lastReadingDate, ')
          ..write('lastReadingValue: $lastReadingValue, ')
          ..write('lastSyncedAt: $lastSyncedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(remoteId, accountNumber, name, address,
      routeId, lastReadingDate, lastReadingValue, lastSyncedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Customer &&
          other.remoteId == this.remoteId &&
          other.accountNumber == this.accountNumber &&
          other.name == this.name &&
          other.address == this.address &&
          other.routeId == this.routeId &&
          other.lastReadingDate == this.lastReadingDate &&
          other.lastReadingValue == this.lastReadingValue &&
          other.lastSyncedAt == this.lastSyncedAt);
}

class CustomersCompanion extends UpdateCompanion<Customer> {
  final Value<int> remoteId;
  final Value<String> accountNumber;
  final Value<String> name;
  final Value<String?> address;
  final Value<int?> routeId;
  final Value<DateTime?> lastReadingDate;
  final Value<double?> lastReadingValue;
  final Value<DateTime> lastSyncedAt;
  const CustomersCompanion({
    this.remoteId = const Value.absent(),
    this.accountNumber = const Value.absent(),
    this.name = const Value.absent(),
    this.address = const Value.absent(),
    this.routeId = const Value.absent(),
    this.lastReadingDate = const Value.absent(),
    this.lastReadingValue = const Value.absent(),
    this.lastSyncedAt = const Value.absent(),
  });
  CustomersCompanion.insert({
    this.remoteId = const Value.absent(),
    required String accountNumber,
    required String name,
    this.address = const Value.absent(),
    this.routeId = const Value.absent(),
    this.lastReadingDate = const Value.absent(),
    this.lastReadingValue = const Value.absent(),
    required DateTime lastSyncedAt,
  })  : accountNumber = Value(accountNumber),
        name = Value(name),
        lastSyncedAt = Value(lastSyncedAt);
  static Insertable<Customer> custom({
    Expression<int>? remoteId,
    Expression<String>? accountNumber,
    Expression<String>? name,
    Expression<String>? address,
    Expression<int>? routeId,
    Expression<DateTime>? lastReadingDate,
    Expression<double>? lastReadingValue,
    Expression<DateTime>? lastSyncedAt,
  }) {
    return RawValuesInsertable({
      if (remoteId != null) 'remote_id': remoteId,
      if (accountNumber != null) 'account_number': accountNumber,
      if (name != null) 'name': name,
      if (address != null) 'address': address,
      if (routeId != null) 'route_id': routeId,
      if (lastReadingDate != null) 'last_reading_date': lastReadingDate,
      if (lastReadingValue != null) 'last_reading_value': lastReadingValue,
      if (lastSyncedAt != null) 'last_synced_at': lastSyncedAt,
    });
  }

  CustomersCompanion copyWith(
      {Value<int>? remoteId,
      Value<String>? accountNumber,
      Value<String>? name,
      Value<String?>? address,
      Value<int?>? routeId,
      Value<DateTime?>? lastReadingDate,
      Value<double?>? lastReadingValue,
      Value<DateTime>? lastSyncedAt}) {
    return CustomersCompanion(
      remoteId: remoteId ?? this.remoteId,
      accountNumber: accountNumber ?? this.accountNumber,
      name: name ?? this.name,
      address: address ?? this.address,
      routeId: routeId ?? this.routeId,
      lastReadingDate: lastReadingDate ?? this.lastReadingDate,
      lastReadingValue: lastReadingValue ?? this.lastReadingValue,
      lastSyncedAt: lastSyncedAt ?? this.lastSyncedAt,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (remoteId.present) {
      map['remote_id'] = Variable<int>(remoteId.value);
    }
    if (accountNumber.present) {
      map['account_number'] = Variable<String>(accountNumber.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (address.present) {
      map['address'] = Variable<String>(address.value);
    }
    if (routeId.present) {
      map['route_id'] = Variable<int>(routeId.value);
    }
    if (lastReadingDate.present) {
      map['last_reading_date'] = Variable<DateTime>(lastReadingDate.value);
    }
    if (lastReadingValue.present) {
      map['last_reading_value'] = Variable<double>(lastReadingValue.value);
    }
    if (lastSyncedAt.present) {
      map['last_synced_at'] = Variable<DateTime>(lastSyncedAt.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CustomersCompanion(')
          ..write('remoteId: $remoteId, ')
          ..write('accountNumber: $accountNumber, ')
          ..write('name: $name, ')
          ..write('address: $address, ')
          ..write('routeId: $routeId, ')
          ..write('lastReadingDate: $lastReadingDate, ')
          ..write('lastReadingValue: $lastReadingValue, ')
          ..write('lastSyncedAt: $lastSyncedAt')
          ..write(')'))
        .toString();
  }
}

class $MetersTable extends Meters with TableInfo<$MetersTable, Meter> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MetersTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _remoteIdMeta =
      const VerificationMeta('remoteId');
  @override
  late final GeneratedColumn<int> remoteId = GeneratedColumn<int>(
      'remote_id', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _meterNumberMeta =
      const VerificationMeta('meterNumber');
  @override
  late final GeneratedColumn<String> meterNumber = GeneratedColumn<String>(
      'meter_number', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _serialNumberMeta =
      const VerificationMeta('serialNumber');
  @override
  late final GeneratedColumn<String> serialNumber = GeneratedColumn<String>(
      'serial_number', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _customerRemoteIdMeta =
      const VerificationMeta('customerRemoteId');
  @override
  late final GeneratedColumn<int> customerRemoteId = GeneratedColumn<int>(
      'customer_remote_id', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: true,
      defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES customers (remote_id)'));
  static const VerificationMeta _meterTypeMeta =
      const VerificationMeta('meterType');
  @override
  late final GeneratedColumn<String> meterType = GeneratedColumn<String>(
      'meter_type', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _paymentTypeMeta =
      const VerificationMeta('paymentType');
  @override
  late final GeneratedColumn<String> paymentType = GeneratedColumn<String>(
      'payment_type', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _communicationTypeMeta =
      const VerificationMeta('communicationType');
  @override
  late final GeneratedColumn<String> communicationType =
      GeneratedColumn<String>('communication_type', aliasedName, true,
          type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _routeIdMeta =
      const VerificationMeta('routeId');
  @override
  late final GeneratedColumn<int> routeId = GeneratedColumn<int>(
      'route_id', aliasedName, true,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _isCouplingMeterMeta =
      const VerificationMeta('isCouplingMeter');
  @override
  late final GeneratedColumn<bool> isCouplingMeter = GeneratedColumn<bool>(
      'is_coupling_meter', aliasedName, false,
      type: DriftSqlType.bool,
      requiredDuringInsert: false,
      defaultConstraints: GeneratedColumn.constraintIsAlways(
          'CHECK ("is_coupling_meter" IN (0, 1))'),
      defaultValue: const Constant(false));
  @override
  List<GeneratedColumn> get $columns => [
        remoteId,
        meterNumber,
        serialNumber,
        customerRemoteId,
        meterType,
        paymentType,
        communicationType,
        routeId,
        isCouplingMeter
      ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'meters';
  @override
  VerificationContext validateIntegrity(Insertable<Meter> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('remote_id')) {
      context.handle(_remoteIdMeta,
          remoteId.isAcceptableOrUnknown(data['remote_id']!, _remoteIdMeta));
    }
    if (data.containsKey('meter_number')) {
      context.handle(
          _meterNumberMeta,
          meterNumber.isAcceptableOrUnknown(
              data['meter_number']!, _meterNumberMeta));
    } else if (isInserting) {
      context.missing(_meterNumberMeta);
    }
    if (data.containsKey('serial_number')) {
      context.handle(
          _serialNumberMeta,
          serialNumber.isAcceptableOrUnknown(
              data['serial_number']!, _serialNumberMeta));
    }
    if (data.containsKey('customer_remote_id')) {
      context.handle(
          _customerRemoteIdMeta,
          customerRemoteId.isAcceptableOrUnknown(
              data['customer_remote_id']!, _customerRemoteIdMeta));
    } else if (isInserting) {
      context.missing(_customerRemoteIdMeta);
    }
    if (data.containsKey('meter_type')) {
      context.handle(_meterTypeMeta,
          meterType.isAcceptableOrUnknown(data['meter_type']!, _meterTypeMeta));
    }
    if (data.containsKey('payment_type')) {
      context.handle(
          _paymentTypeMeta,
          paymentType.isAcceptableOrUnknown(
              data['payment_type']!, _paymentTypeMeta));
    } else if (isInserting) {
      context.missing(_paymentTypeMeta);
    }
    if (data.containsKey('communication_type')) {
      context.handle(
          _communicationTypeMeta,
          communicationType.isAcceptableOrUnknown(
              data['communication_type']!, _communicationTypeMeta));
    }
    if (data.containsKey('route_id')) {
      context.handle(_routeIdMeta,
          routeId.isAcceptableOrUnknown(data['route_id']!, _routeIdMeta));
    }
    if (data.containsKey('is_coupling_meter')) {
      context.handle(
          _isCouplingMeterMeta,
          isCouplingMeter.isAcceptableOrUnknown(
              data['is_coupling_meter']!, _isCouplingMeterMeta));
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {remoteId};
  @override
  Meter map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Meter(
      remoteId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}remote_id'])!,
      meterNumber: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}meter_number'])!,
      serialNumber: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}serial_number']),
      customerRemoteId: attachedDatabase.typeMapping.read(
          DriftSqlType.int, data['${effectivePrefix}customer_remote_id'])!,
      meterType: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}meter_type']),
      paymentType: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}payment_type'])!,
      communicationType: attachedDatabase.typeMapping.read(
          DriftSqlType.string, data['${effectivePrefix}communication_type']),
      routeId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}route_id']),
      isCouplingMeter: attachedDatabase.typeMapping.read(
          DriftSqlType.bool, data['${effectivePrefix}is_coupling_meter'])!,
    );
  }

  @override
  $MetersTable createAlias(String alias) {
    return $MetersTable(attachedDatabase, alias);
  }
}

class Meter extends DataClass implements Insertable<Meter> {
  final int remoteId;
  final String meterNumber;
  final String? serialNumber;
  final int customerRemoteId;
  final String? meterType;
  final String paymentType;
  final String? communicationType;
  final int? routeId;
  final bool isCouplingMeter;
  const Meter(
      {required this.remoteId,
      required this.meterNumber,
      this.serialNumber,
      required this.customerRemoteId,
      this.meterType,
      required this.paymentType,
      this.communicationType,
      this.routeId,
      required this.isCouplingMeter});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['remote_id'] = Variable<int>(remoteId);
    map['meter_number'] = Variable<String>(meterNumber);
    if (!nullToAbsent || serialNumber != null) {
      map['serial_number'] = Variable<String>(serialNumber);
    }
    map['customer_remote_id'] = Variable<int>(customerRemoteId);
    if (!nullToAbsent || meterType != null) {
      map['meter_type'] = Variable<String>(meterType);
    }
    map['payment_type'] = Variable<String>(paymentType);
    if (!nullToAbsent || communicationType != null) {
      map['communication_type'] = Variable<String>(communicationType);
    }
    if (!nullToAbsent || routeId != null) {
      map['route_id'] = Variable<int>(routeId);
    }
    map['is_coupling_meter'] = Variable<bool>(isCouplingMeter);
    return map;
  }

  MetersCompanion toCompanion(bool nullToAbsent) {
    return MetersCompanion(
      remoteId: Value(remoteId),
      meterNumber: Value(meterNumber),
      serialNumber: serialNumber == null && nullToAbsent
          ? const Value.absent()
          : Value(serialNumber),
      customerRemoteId: Value(customerRemoteId),
      meterType: meterType == null && nullToAbsent
          ? const Value.absent()
          : Value(meterType),
      paymentType: Value(paymentType),
      communicationType: communicationType == null && nullToAbsent
          ? const Value.absent()
          : Value(communicationType),
      routeId: routeId == null && nullToAbsent
          ? const Value.absent()
          : Value(routeId),
      isCouplingMeter: Value(isCouplingMeter),
    );
  }

  factory Meter.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Meter(
      remoteId: serializer.fromJson<int>(json['remoteId']),
      meterNumber: serializer.fromJson<String>(json['meterNumber']),
      serialNumber: serializer.fromJson<String?>(json['serialNumber']),
      customerRemoteId: serializer.fromJson<int>(json['customerRemoteId']),
      meterType: serializer.fromJson<String?>(json['meterType']),
      paymentType: serializer.fromJson<String>(json['paymentType']),
      communicationType:
          serializer.fromJson<String?>(json['communicationType']),
      routeId: serializer.fromJson<int?>(json['routeId']),
      isCouplingMeter: serializer.fromJson<bool>(json['isCouplingMeter']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'remoteId': serializer.toJson<int>(remoteId),
      'meterNumber': serializer.toJson<String>(meterNumber),
      'serialNumber': serializer.toJson<String?>(serialNumber),
      'customerRemoteId': serializer.toJson<int>(customerRemoteId),
      'meterType': serializer.toJson<String?>(meterType),
      'paymentType': serializer.toJson<String>(paymentType),
      'communicationType': serializer.toJson<String?>(communicationType),
      'routeId': serializer.toJson<int?>(routeId),
      'isCouplingMeter': serializer.toJson<bool>(isCouplingMeter),
    };
  }

  Meter copyWith(
          {int? remoteId,
          String? meterNumber,
          Value<String?> serialNumber = const Value.absent(),
          int? customerRemoteId,
          Value<String?> meterType = const Value.absent(),
          String? paymentType,
          Value<String?> communicationType = const Value.absent(),
          Value<int?> routeId = const Value.absent(),
          bool? isCouplingMeter}) =>
      Meter(
        remoteId: remoteId ?? this.remoteId,
        meterNumber: meterNumber ?? this.meterNumber,
        serialNumber:
            serialNumber.present ? serialNumber.value : this.serialNumber,
        customerRemoteId: customerRemoteId ?? this.customerRemoteId,
        meterType: meterType.present ? meterType.value : this.meterType,
        paymentType: paymentType ?? this.paymentType,
        communicationType: communicationType.present
            ? communicationType.value
            : this.communicationType,
        routeId: routeId.present ? routeId.value : this.routeId,
        isCouplingMeter: isCouplingMeter ?? this.isCouplingMeter,
      );
  Meter copyWithCompanion(MetersCompanion data) {
    return Meter(
      remoteId: data.remoteId.present ? data.remoteId.value : this.remoteId,
      meterNumber:
          data.meterNumber.present ? data.meterNumber.value : this.meterNumber,
      serialNumber: data.serialNumber.present
          ? data.serialNumber.value
          : this.serialNumber,
      customerRemoteId: data.customerRemoteId.present
          ? data.customerRemoteId.value
          : this.customerRemoteId,
      meterType: data.meterType.present ? data.meterType.value : this.meterType,
      paymentType:
          data.paymentType.present ? data.paymentType.value : this.paymentType,
      communicationType: data.communicationType.present
          ? data.communicationType.value
          : this.communicationType,
      routeId: data.routeId.present ? data.routeId.value : this.routeId,
      isCouplingMeter: data.isCouplingMeter.present
          ? data.isCouplingMeter.value
          : this.isCouplingMeter,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Meter(')
          ..write('remoteId: $remoteId, ')
          ..write('meterNumber: $meterNumber, ')
          ..write('serialNumber: $serialNumber, ')
          ..write('customerRemoteId: $customerRemoteId, ')
          ..write('meterType: $meterType, ')
          ..write('paymentType: $paymentType, ')
          ..write('communicationType: $communicationType, ')
          ..write('routeId: $routeId, ')
          ..write('isCouplingMeter: $isCouplingMeter')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
      remoteId,
      meterNumber,
      serialNumber,
      customerRemoteId,
      meterType,
      paymentType,
      communicationType,
      routeId,
      isCouplingMeter);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Meter &&
          other.remoteId == this.remoteId &&
          other.meterNumber == this.meterNumber &&
          other.serialNumber == this.serialNumber &&
          other.customerRemoteId == this.customerRemoteId &&
          other.meterType == this.meterType &&
          other.paymentType == this.paymentType &&
          other.communicationType == this.communicationType &&
          other.routeId == this.routeId &&
          other.isCouplingMeter == this.isCouplingMeter);
}

class MetersCompanion extends UpdateCompanion<Meter> {
  final Value<int> remoteId;
  final Value<String> meterNumber;
  final Value<String?> serialNumber;
  final Value<int> customerRemoteId;
  final Value<String?> meterType;
  final Value<String> paymentType;
  final Value<String?> communicationType;
  final Value<int?> routeId;
  final Value<bool> isCouplingMeter;
  const MetersCompanion({
    this.remoteId = const Value.absent(),
    this.meterNumber = const Value.absent(),
    this.serialNumber = const Value.absent(),
    this.customerRemoteId = const Value.absent(),
    this.meterType = const Value.absent(),
    this.paymentType = const Value.absent(),
    this.communicationType = const Value.absent(),
    this.routeId = const Value.absent(),
    this.isCouplingMeter = const Value.absent(),
  });
  MetersCompanion.insert({
    this.remoteId = const Value.absent(),
    required String meterNumber,
    this.serialNumber = const Value.absent(),
    required int customerRemoteId,
    this.meterType = const Value.absent(),
    required String paymentType,
    this.communicationType = const Value.absent(),
    this.routeId = const Value.absent(),
    this.isCouplingMeter = const Value.absent(),
  })  : meterNumber = Value(meterNumber),
        customerRemoteId = Value(customerRemoteId),
        paymentType = Value(paymentType);
  static Insertable<Meter> custom({
    Expression<int>? remoteId,
    Expression<String>? meterNumber,
    Expression<String>? serialNumber,
    Expression<int>? customerRemoteId,
    Expression<String>? meterType,
    Expression<String>? paymentType,
    Expression<String>? communicationType,
    Expression<int>? routeId,
    Expression<bool>? isCouplingMeter,
  }) {
    return RawValuesInsertable({
      if (remoteId != null) 'remote_id': remoteId,
      if (meterNumber != null) 'meter_number': meterNumber,
      if (serialNumber != null) 'serial_number': serialNumber,
      if (customerRemoteId != null) 'customer_remote_id': customerRemoteId,
      if (meterType != null) 'meter_type': meterType,
      if (paymentType != null) 'payment_type': paymentType,
      if (communicationType != null) 'communication_type': communicationType,
      if (routeId != null) 'route_id': routeId,
      if (isCouplingMeter != null) 'is_coupling_meter': isCouplingMeter,
    });
  }

  MetersCompanion copyWith(
      {Value<int>? remoteId,
      Value<String>? meterNumber,
      Value<String?>? serialNumber,
      Value<int>? customerRemoteId,
      Value<String?>? meterType,
      Value<String>? paymentType,
      Value<String?>? communicationType,
      Value<int?>? routeId,
      Value<bool>? isCouplingMeter}) {
    return MetersCompanion(
      remoteId: remoteId ?? this.remoteId,
      meterNumber: meterNumber ?? this.meterNumber,
      serialNumber: serialNumber ?? this.serialNumber,
      customerRemoteId: customerRemoteId ?? this.customerRemoteId,
      meterType: meterType ?? this.meterType,
      paymentType: paymentType ?? this.paymentType,
      communicationType: communicationType ?? this.communicationType,
      routeId: routeId ?? this.routeId,
      isCouplingMeter: isCouplingMeter ?? this.isCouplingMeter,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (remoteId.present) {
      map['remote_id'] = Variable<int>(remoteId.value);
    }
    if (meterNumber.present) {
      map['meter_number'] = Variable<String>(meterNumber.value);
    }
    if (serialNumber.present) {
      map['serial_number'] = Variable<String>(serialNumber.value);
    }
    if (customerRemoteId.present) {
      map['customer_remote_id'] = Variable<int>(customerRemoteId.value);
    }
    if (meterType.present) {
      map['meter_type'] = Variable<String>(meterType.value);
    }
    if (paymentType.present) {
      map['payment_type'] = Variable<String>(paymentType.value);
    }
    if (communicationType.present) {
      map['communication_type'] = Variable<String>(communicationType.value);
    }
    if (routeId.present) {
      map['route_id'] = Variable<int>(routeId.value);
    }
    if (isCouplingMeter.present) {
      map['is_coupling_meter'] = Variable<bool>(isCouplingMeter.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MetersCompanion(')
          ..write('remoteId: $remoteId, ')
          ..write('meterNumber: $meterNumber, ')
          ..write('serialNumber: $serialNumber, ')
          ..write('customerRemoteId: $customerRemoteId, ')
          ..write('meterType: $meterType, ')
          ..write('paymentType: $paymentType, ')
          ..write('communicationType: $communicationType, ')
          ..write('routeId: $routeId, ')
          ..write('isCouplingMeter: $isCouplingMeter')
          ..write(')'))
        .toString();
  }
}

class $AssignmentsTable extends Assignments
    with TableInfo<$AssignmentsTable, Assignment> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $AssignmentsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _meterRemoteIdMeta =
      const VerificationMeta('meterRemoteId');
  @override
  late final GeneratedColumn<int> meterRemoteId = GeneratedColumn<int>(
      'meter_remote_id', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: true,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('REFERENCES meters (remote_id)'));
  static const VerificationMeta _periodIdMeta =
      const VerificationMeta('periodId');
  @override
  late final GeneratedColumn<int> periodId = GeneratedColumn<int>(
      'period_id', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
      'status', aliasedName, false,
      type: DriftSqlType.string,
      requiredDuringInsert: false,
      defaultValue: const Constant('pending'));
  static const VerificationMeta _downloadedAtMeta =
      const VerificationMeta('downloadedAt');
  @override
  late final GeneratedColumn<DateTime> downloadedAt = GeneratedColumn<DateTime>(
      'downloaded_at', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns =>
      [id, meterRemoteId, periodId, status, downloadedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'assignments';
  @override
  VerificationContext validateIntegrity(Insertable<Assignment> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('meter_remote_id')) {
      context.handle(
          _meterRemoteIdMeta,
          meterRemoteId.isAcceptableOrUnknown(
              data['meter_remote_id']!, _meterRemoteIdMeta));
    } else if (isInserting) {
      context.missing(_meterRemoteIdMeta);
    }
    if (data.containsKey('period_id')) {
      context.handle(_periodIdMeta,
          periodId.isAcceptableOrUnknown(data['period_id']!, _periodIdMeta));
    } else if (isInserting) {
      context.missing(_periodIdMeta);
    }
    if (data.containsKey('status')) {
      context.handle(_statusMeta,
          status.isAcceptableOrUnknown(data['status']!, _statusMeta));
    }
    if (data.containsKey('downloaded_at')) {
      context.handle(
          _downloadedAtMeta,
          downloadedAt.isAcceptableOrUnknown(
              data['downloaded_at']!, _downloadedAtMeta));
    } else if (isInserting) {
      context.missing(_downloadedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  Assignment map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Assignment(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      meterRemoteId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}meter_remote_id'])!,
      periodId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}period_id'])!,
      status: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}status'])!,
      downloadedAt: attachedDatabase.typeMapping.read(
          DriftSqlType.dateTime, data['${effectivePrefix}downloaded_at'])!,
    );
  }

  @override
  $AssignmentsTable createAlias(String alias) {
    return $AssignmentsTable(attachedDatabase, alias);
  }
}

class Assignment extends DataClass implements Insertable<Assignment> {
  final String id;
  final int meterRemoteId;
  final int periodId;
  final String status;
  final DateTime downloadedAt;
  const Assignment(
      {required this.id,
      required this.meterRemoteId,
      required this.periodId,
      required this.status,
      required this.downloadedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['meter_remote_id'] = Variable<int>(meterRemoteId);
    map['period_id'] = Variable<int>(periodId);
    map['status'] = Variable<String>(status);
    map['downloaded_at'] = Variable<DateTime>(downloadedAt);
    return map;
  }

  AssignmentsCompanion toCompanion(bool nullToAbsent) {
    return AssignmentsCompanion(
      id: Value(id),
      meterRemoteId: Value(meterRemoteId),
      periodId: Value(periodId),
      status: Value(status),
      downloadedAt: Value(downloadedAt),
    );
  }

  factory Assignment.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Assignment(
      id: serializer.fromJson<String>(json['id']),
      meterRemoteId: serializer.fromJson<int>(json['meterRemoteId']),
      periodId: serializer.fromJson<int>(json['periodId']),
      status: serializer.fromJson<String>(json['status']),
      downloadedAt: serializer.fromJson<DateTime>(json['downloadedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'meterRemoteId': serializer.toJson<int>(meterRemoteId),
      'periodId': serializer.toJson<int>(periodId),
      'status': serializer.toJson<String>(status),
      'downloadedAt': serializer.toJson<DateTime>(downloadedAt),
    };
  }

  Assignment copyWith(
          {String? id,
          int? meterRemoteId,
          int? periodId,
          String? status,
          DateTime? downloadedAt}) =>
      Assignment(
        id: id ?? this.id,
        meterRemoteId: meterRemoteId ?? this.meterRemoteId,
        periodId: periodId ?? this.periodId,
        status: status ?? this.status,
        downloadedAt: downloadedAt ?? this.downloadedAt,
      );
  Assignment copyWithCompanion(AssignmentsCompanion data) {
    return Assignment(
      id: data.id.present ? data.id.value : this.id,
      meterRemoteId: data.meterRemoteId.present
          ? data.meterRemoteId.value
          : this.meterRemoteId,
      periodId: data.periodId.present ? data.periodId.value : this.periodId,
      status: data.status.present ? data.status.value : this.status,
      downloadedAt: data.downloadedAt.present
          ? data.downloadedAt.value
          : this.downloadedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Assignment(')
          ..write('id: $id, ')
          ..write('meterRemoteId: $meterRemoteId, ')
          ..write('periodId: $periodId, ')
          ..write('status: $status, ')
          ..write('downloadedAt: $downloadedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(id, meterRemoteId, periodId, status, downloadedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Assignment &&
          other.id == this.id &&
          other.meterRemoteId == this.meterRemoteId &&
          other.periodId == this.periodId &&
          other.status == this.status &&
          other.downloadedAt == this.downloadedAt);
}

class AssignmentsCompanion extends UpdateCompanion<Assignment> {
  final Value<String> id;
  final Value<int> meterRemoteId;
  final Value<int> periodId;
  final Value<String> status;
  final Value<DateTime> downloadedAt;
  final Value<int> rowid;
  const AssignmentsCompanion({
    this.id = const Value.absent(),
    this.meterRemoteId = const Value.absent(),
    this.periodId = const Value.absent(),
    this.status = const Value.absent(),
    this.downloadedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  AssignmentsCompanion.insert({
    required String id,
    required int meterRemoteId,
    required int periodId,
    this.status = const Value.absent(),
    required DateTime downloadedAt,
    this.rowid = const Value.absent(),
  })  : id = Value(id),
        meterRemoteId = Value(meterRemoteId),
        periodId = Value(periodId),
        downloadedAt = Value(downloadedAt);
  static Insertable<Assignment> custom({
    Expression<String>? id,
    Expression<int>? meterRemoteId,
    Expression<int>? periodId,
    Expression<String>? status,
    Expression<DateTime>? downloadedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (meterRemoteId != null) 'meter_remote_id': meterRemoteId,
      if (periodId != null) 'period_id': periodId,
      if (status != null) 'status': status,
      if (downloadedAt != null) 'downloaded_at': downloadedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  AssignmentsCompanion copyWith(
      {Value<String>? id,
      Value<int>? meterRemoteId,
      Value<int>? periodId,
      Value<String>? status,
      Value<DateTime>? downloadedAt,
      Value<int>? rowid}) {
    return AssignmentsCompanion(
      id: id ?? this.id,
      meterRemoteId: meterRemoteId ?? this.meterRemoteId,
      periodId: periodId ?? this.periodId,
      status: status ?? this.status,
      downloadedAt: downloadedAt ?? this.downloadedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (meterRemoteId.present) {
      map['meter_remote_id'] = Variable<int>(meterRemoteId.value);
    }
    if (periodId.present) {
      map['period_id'] = Variable<int>(periodId.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (downloadedAt.present) {
      map['downloaded_at'] = Variable<DateTime>(downloadedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('AssignmentsCompanion(')
          ..write('id: $id, ')
          ..write('meterRemoteId: $meterRemoteId, ')
          ..write('periodId: $periodId, ')
          ..write('status: $status, ')
          ..write('downloadedAt: $downloadedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $PeriodsTable extends Periods with TableInfo<$PeriodsTable, Period> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $PeriodsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
      'id', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
      'name', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _dateStartMeta =
      const VerificationMeta('dateStart');
  @override
  late final GeneratedColumn<DateTime> dateStart = GeneratedColumn<DateTime>(
      'date_start', aliasedName, true,
      type: DriftSqlType.dateTime, requiredDuringInsert: false);
  static const VerificationMeta _dateEndMeta =
      const VerificationMeta('dateEnd');
  @override
  late final GeneratedColumn<DateTime> dateEnd = GeneratedColumn<DateTime>(
      'date_end', aliasedName, true,
      type: DriftSqlType.dateTime, requiredDuringInsert: false);
  static const VerificationMeta _isCurrentMeta =
      const VerificationMeta('isCurrent');
  @override
  late final GeneratedColumn<bool> isCurrent = GeneratedColumn<bool>(
      'is_current', aliasedName, false,
      type: DriftSqlType.bool,
      requiredDuringInsert: false,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('CHECK ("is_current" IN (0, 1))'),
      defaultValue: const Constant(false));
  @override
  List<GeneratedColumn> get $columns =>
      [id, name, dateStart, dateEnd, isCurrent];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'periods';
  @override
  VerificationContext validateIntegrity(Insertable<Period> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('name')) {
      context.handle(
          _nameMeta, name.isAcceptableOrUnknown(data['name']!, _nameMeta));
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('date_start')) {
      context.handle(_dateStartMeta,
          dateStart.isAcceptableOrUnknown(data['date_start']!, _dateStartMeta));
    }
    if (data.containsKey('date_end')) {
      context.handle(_dateEndMeta,
          dateEnd.isAcceptableOrUnknown(data['date_end']!, _dateEndMeta));
    }
    if (data.containsKey('is_current')) {
      context.handle(_isCurrentMeta,
          isCurrent.isAcceptableOrUnknown(data['is_current']!, _isCurrentMeta));
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  Period map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Period(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}id'])!,
      name: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}name'])!,
      dateStart: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}date_start']),
      dateEnd: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}date_end']),
      isCurrent: attachedDatabase.typeMapping
          .read(DriftSqlType.bool, data['${effectivePrefix}is_current'])!,
    );
  }

  @override
  $PeriodsTable createAlias(String alias) {
    return $PeriodsTable(attachedDatabase, alias);
  }
}

class Period extends DataClass implements Insertable<Period> {
  final int id;
  final String name;
  final DateTime? dateStart;
  final DateTime? dateEnd;
  final bool isCurrent;
  const Period(
      {required this.id,
      required this.name,
      this.dateStart,
      this.dateEnd,
      required this.isCurrent});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['name'] = Variable<String>(name);
    if (!nullToAbsent || dateStart != null) {
      map['date_start'] = Variable<DateTime>(dateStart);
    }
    if (!nullToAbsent || dateEnd != null) {
      map['date_end'] = Variable<DateTime>(dateEnd);
    }
    map['is_current'] = Variable<bool>(isCurrent);
    return map;
  }

  PeriodsCompanion toCompanion(bool nullToAbsent) {
    return PeriodsCompanion(
      id: Value(id),
      name: Value(name),
      dateStart: dateStart == null && nullToAbsent
          ? const Value.absent()
          : Value(dateStart),
      dateEnd: dateEnd == null && nullToAbsent
          ? const Value.absent()
          : Value(dateEnd),
      isCurrent: Value(isCurrent),
    );
  }

  factory Period.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Period(
      id: serializer.fromJson<int>(json['id']),
      name: serializer.fromJson<String>(json['name']),
      dateStart: serializer.fromJson<DateTime?>(json['dateStart']),
      dateEnd: serializer.fromJson<DateTime?>(json['dateEnd']),
      isCurrent: serializer.fromJson<bool>(json['isCurrent']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'name': serializer.toJson<String>(name),
      'dateStart': serializer.toJson<DateTime?>(dateStart),
      'dateEnd': serializer.toJson<DateTime?>(dateEnd),
      'isCurrent': serializer.toJson<bool>(isCurrent),
    };
  }

  Period copyWith(
          {int? id,
          String? name,
          Value<DateTime?> dateStart = const Value.absent(),
          Value<DateTime?> dateEnd = const Value.absent(),
          bool? isCurrent}) =>
      Period(
        id: id ?? this.id,
        name: name ?? this.name,
        dateStart: dateStart.present ? dateStart.value : this.dateStart,
        dateEnd: dateEnd.present ? dateEnd.value : this.dateEnd,
        isCurrent: isCurrent ?? this.isCurrent,
      );
  Period copyWithCompanion(PeriodsCompanion data) {
    return Period(
      id: data.id.present ? data.id.value : this.id,
      name: data.name.present ? data.name.value : this.name,
      dateStart: data.dateStart.present ? data.dateStart.value : this.dateStart,
      dateEnd: data.dateEnd.present ? data.dateEnd.value : this.dateEnd,
      isCurrent: data.isCurrent.present ? data.isCurrent.value : this.isCurrent,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Period(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('dateStart: $dateStart, ')
          ..write('dateEnd: $dateEnd, ')
          ..write('isCurrent: $isCurrent')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(id, name, dateStart, dateEnd, isCurrent);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Period &&
          other.id == this.id &&
          other.name == this.name &&
          other.dateStart == this.dateStart &&
          other.dateEnd == this.dateEnd &&
          other.isCurrent == this.isCurrent);
}

class PeriodsCompanion extends UpdateCompanion<Period> {
  final Value<int> id;
  final Value<String> name;
  final Value<DateTime?> dateStart;
  final Value<DateTime?> dateEnd;
  final Value<bool> isCurrent;
  const PeriodsCompanion({
    this.id = const Value.absent(),
    this.name = const Value.absent(),
    this.dateStart = const Value.absent(),
    this.dateEnd = const Value.absent(),
    this.isCurrent = const Value.absent(),
  });
  PeriodsCompanion.insert({
    this.id = const Value.absent(),
    required String name,
    this.dateStart = const Value.absent(),
    this.dateEnd = const Value.absent(),
    this.isCurrent = const Value.absent(),
  }) : name = Value(name);
  static Insertable<Period> custom({
    Expression<int>? id,
    Expression<String>? name,
    Expression<DateTime>? dateStart,
    Expression<DateTime>? dateEnd,
    Expression<bool>? isCurrent,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (name != null) 'name': name,
      if (dateStart != null) 'date_start': dateStart,
      if (dateEnd != null) 'date_end': dateEnd,
      if (isCurrent != null) 'is_current': isCurrent,
    });
  }

  PeriodsCompanion copyWith(
      {Value<int>? id,
      Value<String>? name,
      Value<DateTime?>? dateStart,
      Value<DateTime?>? dateEnd,
      Value<bool>? isCurrent}) {
    return PeriodsCompanion(
      id: id ?? this.id,
      name: name ?? this.name,
      dateStart: dateStart ?? this.dateStart,
      dateEnd: dateEnd ?? this.dateEnd,
      isCurrent: isCurrent ?? this.isCurrent,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (dateStart.present) {
      map['date_start'] = Variable<DateTime>(dateStart.value);
    }
    if (dateEnd.present) {
      map['date_end'] = Variable<DateTime>(dateEnd.value);
    }
    if (isCurrent.present) {
      map['is_current'] = Variable<bool>(isCurrent.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('PeriodsCompanion(')
          ..write('id: $id, ')
          ..write('name: $name, ')
          ..write('dateStart: $dateStart, ')
          ..write('dateEnd: $dateEnd, ')
          ..write('isCurrent: $isCurrent')
          ..write(')'))
        .toString();
  }
}

class $SyncBatchesTable extends SyncBatches
    with TableInfo<$SyncBatchesTable, SyncBatche> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SyncBatchesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
      'status', aliasedName, false,
      type: DriftSqlType.string,
      requiredDuringInsert: false,
      defaultValue: const Constant('pending'));
  static const VerificationMeta _archivePathMeta =
      const VerificationMeta('archivePath');
  @override
  late final GeneratedColumn<String> archivePath = GeneratedColumn<String>(
      'archive_path', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _readingCountMeta =
      const VerificationMeta('readingCount');
  @override
  late final GeneratedColumn<int> readingCount = GeneratedColumn<int>(
      'reading_count', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _retryCountMeta =
      const VerificationMeta('retryCount');
  @override
  late final GeneratedColumn<int> retryCount = GeneratedColumn<int>(
      'retry_count', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: false,
      defaultValue: const Constant(0));
  static const VerificationMeta _lastErrorMeta =
      const VerificationMeta('lastError');
  @override
  late final GeneratedColumn<String> lastError = GeneratedColumn<String>(
      'last_error', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _createdAtMeta =
      const VerificationMeta('createdAt');
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
      'created_at', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  static const VerificationMeta _lastAttemptAtMeta =
      const VerificationMeta('lastAttemptAt');
  @override
  late final GeneratedColumn<DateTime> lastAttemptAt =
      GeneratedColumn<DateTime>('last_attempt_at', aliasedName, true,
          type: DriftSqlType.dateTime, requiredDuringInsert: false);
  @override
  List<GeneratedColumn> get $columns => [
        id,
        status,
        archivePath,
        readingCount,
        retryCount,
        lastError,
        createdAt,
        lastAttemptAt
      ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'sync_batches';
  @override
  VerificationContext validateIntegrity(Insertable<SyncBatche> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('status')) {
      context.handle(_statusMeta,
          status.isAcceptableOrUnknown(data['status']!, _statusMeta));
    }
    if (data.containsKey('archive_path')) {
      context.handle(
          _archivePathMeta,
          archivePath.isAcceptableOrUnknown(
              data['archive_path']!, _archivePathMeta));
    }
    if (data.containsKey('reading_count')) {
      context.handle(
          _readingCountMeta,
          readingCount.isAcceptableOrUnknown(
              data['reading_count']!, _readingCountMeta));
    } else if (isInserting) {
      context.missing(_readingCountMeta);
    }
    if (data.containsKey('retry_count')) {
      context.handle(
          _retryCountMeta,
          retryCount.isAcceptableOrUnknown(
              data['retry_count']!, _retryCountMeta));
    }
    if (data.containsKey('last_error')) {
      context.handle(_lastErrorMeta,
          lastError.isAcceptableOrUnknown(data['last_error']!, _lastErrorMeta));
    }
    if (data.containsKey('created_at')) {
      context.handle(_createdAtMeta,
          createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta));
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('last_attempt_at')) {
      context.handle(
          _lastAttemptAtMeta,
          lastAttemptAt.isAcceptableOrUnknown(
              data['last_attempt_at']!, _lastAttemptAtMeta));
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  SyncBatche map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SyncBatche(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      status: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}status'])!,
      archivePath: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}archive_path']),
      readingCount: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}reading_count'])!,
      retryCount: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}retry_count'])!,
      lastError: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}last_error']),
      createdAt: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}created_at'])!,
      lastAttemptAt: attachedDatabase.typeMapping.read(
          DriftSqlType.dateTime, data['${effectivePrefix}last_attempt_at']),
    );
  }

  @override
  $SyncBatchesTable createAlias(String alias) {
    return $SyncBatchesTable(attachedDatabase, alias);
  }
}

class SyncBatche extends DataClass implements Insertable<SyncBatche> {
  final String id;
  final String status;
  final String? archivePath;
  final int readingCount;
  final int retryCount;
  final String? lastError;
  final DateTime createdAt;
  final DateTime? lastAttemptAt;
  const SyncBatche(
      {required this.id,
      required this.status,
      this.archivePath,
      required this.readingCount,
      required this.retryCount,
      this.lastError,
      required this.createdAt,
      this.lastAttemptAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['status'] = Variable<String>(status);
    if (!nullToAbsent || archivePath != null) {
      map['archive_path'] = Variable<String>(archivePath);
    }
    map['reading_count'] = Variable<int>(readingCount);
    map['retry_count'] = Variable<int>(retryCount);
    if (!nullToAbsent || lastError != null) {
      map['last_error'] = Variable<String>(lastError);
    }
    map['created_at'] = Variable<DateTime>(createdAt);
    if (!nullToAbsent || lastAttemptAt != null) {
      map['last_attempt_at'] = Variable<DateTime>(lastAttemptAt);
    }
    return map;
  }

  SyncBatchesCompanion toCompanion(bool nullToAbsent) {
    return SyncBatchesCompanion(
      id: Value(id),
      status: Value(status),
      archivePath: archivePath == null && nullToAbsent
          ? const Value.absent()
          : Value(archivePath),
      readingCount: Value(readingCount),
      retryCount: Value(retryCount),
      lastError: lastError == null && nullToAbsent
          ? const Value.absent()
          : Value(lastError),
      createdAt: Value(createdAt),
      lastAttemptAt: lastAttemptAt == null && nullToAbsent
          ? const Value.absent()
          : Value(lastAttemptAt),
    );
  }

  factory SyncBatche.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SyncBatche(
      id: serializer.fromJson<String>(json['id']),
      status: serializer.fromJson<String>(json['status']),
      archivePath: serializer.fromJson<String?>(json['archivePath']),
      readingCount: serializer.fromJson<int>(json['readingCount']),
      retryCount: serializer.fromJson<int>(json['retryCount']),
      lastError: serializer.fromJson<String?>(json['lastError']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      lastAttemptAt: serializer.fromJson<DateTime?>(json['lastAttemptAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'status': serializer.toJson<String>(status),
      'archivePath': serializer.toJson<String?>(archivePath),
      'readingCount': serializer.toJson<int>(readingCount),
      'retryCount': serializer.toJson<int>(retryCount),
      'lastError': serializer.toJson<String?>(lastError),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'lastAttemptAt': serializer.toJson<DateTime?>(lastAttemptAt),
    };
  }

  SyncBatche copyWith(
          {String? id,
          String? status,
          Value<String?> archivePath = const Value.absent(),
          int? readingCount,
          int? retryCount,
          Value<String?> lastError = const Value.absent(),
          DateTime? createdAt,
          Value<DateTime?> lastAttemptAt = const Value.absent()}) =>
      SyncBatche(
        id: id ?? this.id,
        status: status ?? this.status,
        archivePath: archivePath.present ? archivePath.value : this.archivePath,
        readingCount: readingCount ?? this.readingCount,
        retryCount: retryCount ?? this.retryCount,
        lastError: lastError.present ? lastError.value : this.lastError,
        createdAt: createdAt ?? this.createdAt,
        lastAttemptAt:
            lastAttemptAt.present ? lastAttemptAt.value : this.lastAttemptAt,
      );
  SyncBatche copyWithCompanion(SyncBatchesCompanion data) {
    return SyncBatche(
      id: data.id.present ? data.id.value : this.id,
      status: data.status.present ? data.status.value : this.status,
      archivePath:
          data.archivePath.present ? data.archivePath.value : this.archivePath,
      readingCount: data.readingCount.present
          ? data.readingCount.value
          : this.readingCount,
      retryCount:
          data.retryCount.present ? data.retryCount.value : this.retryCount,
      lastError: data.lastError.present ? data.lastError.value : this.lastError,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      lastAttemptAt: data.lastAttemptAt.present
          ? data.lastAttemptAt.value
          : this.lastAttemptAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SyncBatche(')
          ..write('id: $id, ')
          ..write('status: $status, ')
          ..write('archivePath: $archivePath, ')
          ..write('readingCount: $readingCount, ')
          ..write('retryCount: $retryCount, ')
          ..write('lastError: $lastError, ')
          ..write('createdAt: $createdAt, ')
          ..write('lastAttemptAt: $lastAttemptAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(id, status, archivePath, readingCount,
      retryCount, lastError, createdAt, lastAttemptAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SyncBatche &&
          other.id == this.id &&
          other.status == this.status &&
          other.archivePath == this.archivePath &&
          other.readingCount == this.readingCount &&
          other.retryCount == this.retryCount &&
          other.lastError == this.lastError &&
          other.createdAt == this.createdAt &&
          other.lastAttemptAt == this.lastAttemptAt);
}

class SyncBatchesCompanion extends UpdateCompanion<SyncBatche> {
  final Value<String> id;
  final Value<String> status;
  final Value<String?> archivePath;
  final Value<int> readingCount;
  final Value<int> retryCount;
  final Value<String?> lastError;
  final Value<DateTime> createdAt;
  final Value<DateTime?> lastAttemptAt;
  final Value<int> rowid;
  const SyncBatchesCompanion({
    this.id = const Value.absent(),
    this.status = const Value.absent(),
    this.archivePath = const Value.absent(),
    this.readingCount = const Value.absent(),
    this.retryCount = const Value.absent(),
    this.lastError = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.lastAttemptAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  SyncBatchesCompanion.insert({
    required String id,
    this.status = const Value.absent(),
    this.archivePath = const Value.absent(),
    required int readingCount,
    this.retryCount = const Value.absent(),
    this.lastError = const Value.absent(),
    required DateTime createdAt,
    this.lastAttemptAt = const Value.absent(),
    this.rowid = const Value.absent(),
  })  : id = Value(id),
        readingCount = Value(readingCount),
        createdAt = Value(createdAt);
  static Insertable<SyncBatche> custom({
    Expression<String>? id,
    Expression<String>? status,
    Expression<String>? archivePath,
    Expression<int>? readingCount,
    Expression<int>? retryCount,
    Expression<String>? lastError,
    Expression<DateTime>? createdAt,
    Expression<DateTime>? lastAttemptAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (status != null) 'status': status,
      if (archivePath != null) 'archive_path': archivePath,
      if (readingCount != null) 'reading_count': readingCount,
      if (retryCount != null) 'retry_count': retryCount,
      if (lastError != null) 'last_error': lastError,
      if (createdAt != null) 'created_at': createdAt,
      if (lastAttemptAt != null) 'last_attempt_at': lastAttemptAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  SyncBatchesCompanion copyWith(
      {Value<String>? id,
      Value<String>? status,
      Value<String?>? archivePath,
      Value<int>? readingCount,
      Value<int>? retryCount,
      Value<String?>? lastError,
      Value<DateTime>? createdAt,
      Value<DateTime?>? lastAttemptAt,
      Value<int>? rowid}) {
    return SyncBatchesCompanion(
      id: id ?? this.id,
      status: status ?? this.status,
      archivePath: archivePath ?? this.archivePath,
      readingCount: readingCount ?? this.readingCount,
      retryCount: retryCount ?? this.retryCount,
      lastError: lastError ?? this.lastError,
      createdAt: createdAt ?? this.createdAt,
      lastAttemptAt: lastAttemptAt ?? this.lastAttemptAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (archivePath.present) {
      map['archive_path'] = Variable<String>(archivePath.value);
    }
    if (readingCount.present) {
      map['reading_count'] = Variable<int>(readingCount.value);
    }
    if (retryCount.present) {
      map['retry_count'] = Variable<int>(retryCount.value);
    }
    if (lastError.present) {
      map['last_error'] = Variable<String>(lastError.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (lastAttemptAt.present) {
      map['last_attempt_at'] = Variable<DateTime>(lastAttemptAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SyncBatchesCompanion(')
          ..write('id: $id, ')
          ..write('status: $status, ')
          ..write('archivePath: $archivePath, ')
          ..write('readingCount: $readingCount, ')
          ..write('retryCount: $retryCount, ')
          ..write('lastError: $lastError, ')
          ..write('createdAt: $createdAt, ')
          ..write('lastAttemptAt: $lastAttemptAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ReadingsTable extends Readings with TableInfo<$ReadingsTable, Reading> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ReadingsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _remoteIdMeta =
      const VerificationMeta('remoteId');
  @override
  late final GeneratedColumn<int> remoteId = GeneratedColumn<int>(
      'remote_id', aliasedName, true,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _meterRemoteIdMeta =
      const VerificationMeta('meterRemoteId');
  @override
  late final GeneratedColumn<int> meterRemoteId = GeneratedColumn<int>(
      'meter_remote_id', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: true,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('REFERENCES meters (remote_id)'));
  static const VerificationMeta _readingValueMeta =
      const VerificationMeta('readingValue');
  @override
  late final GeneratedColumn<double> readingValue = GeneratedColumn<double>(
      'reading_value', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _readingDateMeta =
      const VerificationMeta('readingDate');
  @override
  late final GeneratedColumn<DateTime> readingDate = GeneratedColumn<DateTime>(
      'reading_date', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  static const VerificationMeta _capturedPeriodIdMeta =
      const VerificationMeta('capturedPeriodId');
  @override
  late final GeneratedColumn<int> capturedPeriodId = GeneratedColumn<int>(
      'captured_period_id', aliasedName, true,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _readingCategoryMeta =
      const VerificationMeta('readingCategory');
  @override
  late final GeneratedColumn<String> readingCategory = GeneratedColumn<String>(
      'reading_category', aliasedName, false,
      type: DriftSqlType.string,
      requiredDuringInsert: false,
      defaultValue: const Constant('customer'));
  static const VerificationMeta _isEstimatedMeta =
      const VerificationMeta('isEstimated');
  @override
  late final GeneratedColumn<bool> isEstimated = GeneratedColumn<bool>(
      'is_estimated', aliasedName, false,
      type: DriftSqlType.bool,
      requiredDuringInsert: false,
      defaultConstraints: GeneratedColumn.constraintIsAlways(
          'CHECK ("is_estimated" IN (0, 1))'),
      defaultValue: const Constant(false));
  static const VerificationMeta _remarksMeta =
      const VerificationMeta('remarks');
  @override
  late final GeneratedColumn<String> remarks = GeneratedColumn<String>(
      'remarks', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _imageLocalPathMeta =
      const VerificationMeta('imageLocalPath');
  @override
  late final GeneratedColumn<String> imageLocalPath = GeneratedColumn<String>(
      'image_local_path', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _imageSecondaryLocalPathMeta =
      const VerificationMeta('imageSecondaryLocalPath');
  @override
  late final GeneratedColumn<String> imageSecondaryLocalPath =
      GeneratedColumn<String>('image_secondary_local_path', aliasedName, true,
          type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _imageAttachmentRemoteIdMeta =
      const VerificationMeta('imageAttachmentRemoteId');
  @override
  late final GeneratedColumn<int> imageAttachmentRemoteId =
      GeneratedColumn<int>('image_attachment_remote_id', aliasedName, true,
          type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _syncStatusMeta =
      const VerificationMeta('syncStatus');
  @override
  late final GeneratedColumn<String> syncStatus = GeneratedColumn<String>(
      'sync_status', aliasedName, false,
      type: DriftSqlType.string,
      requiredDuringInsert: false,
      defaultValue: const Constant('draft'));
  static const VerificationMeta _syncAttemptsMeta =
      const VerificationMeta('syncAttempts');
  @override
  late final GeneratedColumn<int> syncAttempts = GeneratedColumn<int>(
      'sync_attempts', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: false,
      defaultValue: const Constant(0));
  static const VerificationMeta _syncBatchIdMeta =
      const VerificationMeta('syncBatchId');
  @override
  late final GeneratedColumn<String> syncBatchId = GeneratedColumn<String>(
      'sync_batch_id', aliasedName, true,
      type: DriftSqlType.string,
      requiredDuringInsert: false,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('REFERENCES sync_batches (id)'));
  static const VerificationMeta _lastErrorMeta =
      const VerificationMeta('lastError');
  @override
  late final GeneratedColumn<String> lastError = GeneratedColumn<String>(
      'last_error', aliasedName, true,
      type: DriftSqlType.string, requiredDuringInsert: false);
  static const VerificationMeta _createdAtMeta =
      const VerificationMeta('createdAt');
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
      'created_at', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  static const VerificationMeta _updatedAtMeta =
      const VerificationMeta('updatedAt');
  @override
  late final GeneratedColumn<DateTime> updatedAt = GeneratedColumn<DateTime>(
      'updated_at', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns => [
        id,
        remoteId,
        meterRemoteId,
        readingValue,
        readingDate,
        capturedPeriodId,
        readingCategory,
        isEstimated,
        remarks,
        imageLocalPath,
        imageSecondaryLocalPath,
        imageAttachmentRemoteId,
        syncStatus,
        syncAttempts,
        syncBatchId,
        lastError,
        createdAt,
        updatedAt
      ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'readings';
  @override
  VerificationContext validateIntegrity(Insertable<Reading> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('remote_id')) {
      context.handle(_remoteIdMeta,
          remoteId.isAcceptableOrUnknown(data['remote_id']!, _remoteIdMeta));
    }
    if (data.containsKey('meter_remote_id')) {
      context.handle(
          _meterRemoteIdMeta,
          meterRemoteId.isAcceptableOrUnknown(
              data['meter_remote_id']!, _meterRemoteIdMeta));
    } else if (isInserting) {
      context.missing(_meterRemoteIdMeta);
    }
    if (data.containsKey('reading_value')) {
      context.handle(
          _readingValueMeta,
          readingValue.isAcceptableOrUnknown(
              data['reading_value']!, _readingValueMeta));
    } else if (isInserting) {
      context.missing(_readingValueMeta);
    }
    if (data.containsKey('reading_date')) {
      context.handle(
          _readingDateMeta,
          readingDate.isAcceptableOrUnknown(
              data['reading_date']!, _readingDateMeta));
    } else if (isInserting) {
      context.missing(_readingDateMeta);
    }
    if (data.containsKey('captured_period_id')) {
      context.handle(
          _capturedPeriodIdMeta,
          capturedPeriodId.isAcceptableOrUnknown(
              data['captured_period_id']!, _capturedPeriodIdMeta));
    }
    if (data.containsKey('reading_category')) {
      context.handle(
          _readingCategoryMeta,
          readingCategory.isAcceptableOrUnknown(
              data['reading_category']!, _readingCategoryMeta));
    }
    if (data.containsKey('is_estimated')) {
      context.handle(
          _isEstimatedMeta,
          isEstimated.isAcceptableOrUnknown(
              data['is_estimated']!, _isEstimatedMeta));
    }
    if (data.containsKey('remarks')) {
      context.handle(_remarksMeta,
          remarks.isAcceptableOrUnknown(data['remarks']!, _remarksMeta));
    }
    if (data.containsKey('image_local_path')) {
      context.handle(
          _imageLocalPathMeta,
          imageLocalPath.isAcceptableOrUnknown(
              data['image_local_path']!, _imageLocalPathMeta));
    }
    if (data.containsKey('image_secondary_local_path')) {
      context.handle(
          _imageSecondaryLocalPathMeta,
          imageSecondaryLocalPath.isAcceptableOrUnknown(
              data['image_secondary_local_path']!,
              _imageSecondaryLocalPathMeta));
    }
    if (data.containsKey('image_attachment_remote_id')) {
      context.handle(
          _imageAttachmentRemoteIdMeta,
          imageAttachmentRemoteId.isAcceptableOrUnknown(
              data['image_attachment_remote_id']!,
              _imageAttachmentRemoteIdMeta));
    }
    if (data.containsKey('sync_status')) {
      context.handle(
          _syncStatusMeta,
          syncStatus.isAcceptableOrUnknown(
              data['sync_status']!, _syncStatusMeta));
    }
    if (data.containsKey('sync_attempts')) {
      context.handle(
          _syncAttemptsMeta,
          syncAttempts.isAcceptableOrUnknown(
              data['sync_attempts']!, _syncAttemptsMeta));
    }
    if (data.containsKey('sync_batch_id')) {
      context.handle(
          _syncBatchIdMeta,
          syncBatchId.isAcceptableOrUnknown(
              data['sync_batch_id']!, _syncBatchIdMeta));
    }
    if (data.containsKey('last_error')) {
      context.handle(_lastErrorMeta,
          lastError.isAcceptableOrUnknown(data['last_error']!, _lastErrorMeta));
    }
    if (data.containsKey('created_at')) {
      context.handle(_createdAtMeta,
          createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta));
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('updated_at')) {
      context.handle(_updatedAtMeta,
          updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta));
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  Reading map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Reading(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      remoteId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}remote_id']),
      meterRemoteId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}meter_remote_id'])!,
      readingValue: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}reading_value'])!,
      readingDate: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}reading_date'])!,
      capturedPeriodId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}captured_period_id']),
      readingCategory: attachedDatabase.typeMapping.read(
          DriftSqlType.string, data['${effectivePrefix}reading_category'])!,
      isEstimated: attachedDatabase.typeMapping
          .read(DriftSqlType.bool, data['${effectivePrefix}is_estimated'])!,
      remarks: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}remarks']),
      imageLocalPath: attachedDatabase.typeMapping.read(
          DriftSqlType.string, data['${effectivePrefix}image_local_path']),
      imageSecondaryLocalPath: attachedDatabase.typeMapping.read(
          DriftSqlType.string,
          data['${effectivePrefix}image_secondary_local_path']),
      imageAttachmentRemoteId: attachedDatabase.typeMapping.read(
          DriftSqlType.int,
          data['${effectivePrefix}image_attachment_remote_id']),
      syncStatus: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}sync_status'])!,
      syncAttempts: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}sync_attempts'])!,
      syncBatchId: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}sync_batch_id']),
      lastError: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}last_error']),
      createdAt: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}created_at'])!,
      updatedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}updated_at'])!,
    );
  }

  @override
  $ReadingsTable createAlias(String alias) {
    return $ReadingsTable(attachedDatabase, alias);
  }
}

class Reading extends DataClass implements Insertable<Reading> {
  final String id;
  final int? remoteId;
  final int meterRemoteId;
  final double readingValue;
  final DateTime readingDate;

  /// بصمة الفترة (date.range id) المفتوحة وقت التقاط القراءة ميدانياً —
  /// يمنع SyncEngine من إلصاق قراءة قديمة غير مُزامَنة بفترة جديدة مختلفة
  /// عند الرفع. nullable لتوافق الصفوف القديمة قبل هذا العمود (migration v3).
  final int? capturedPeriodId;
  final String readingCategory;
  final bool isEstimated;
  final String? remarks;
  final String? imageLocalPath;
  final String? imageSecondaryLocalPath;
  final int? imageAttachmentRemoteId;
  final String syncStatus;
  final int syncAttempts;
  final String? syncBatchId;
  final String? lastError;
  final DateTime createdAt;
  final DateTime updatedAt;
  const Reading(
      {required this.id,
      this.remoteId,
      required this.meterRemoteId,
      required this.readingValue,
      required this.readingDate,
      this.capturedPeriodId,
      required this.readingCategory,
      required this.isEstimated,
      this.remarks,
      this.imageLocalPath,
      this.imageSecondaryLocalPath,
      this.imageAttachmentRemoteId,
      required this.syncStatus,
      required this.syncAttempts,
      this.syncBatchId,
      this.lastError,
      required this.createdAt,
      required this.updatedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    if (!nullToAbsent || remoteId != null) {
      map['remote_id'] = Variable<int>(remoteId);
    }
    map['meter_remote_id'] = Variable<int>(meterRemoteId);
    map['reading_value'] = Variable<double>(readingValue);
    map['reading_date'] = Variable<DateTime>(readingDate);
    if (!nullToAbsent || capturedPeriodId != null) {
      map['captured_period_id'] = Variable<int>(capturedPeriodId);
    }
    map['reading_category'] = Variable<String>(readingCategory);
    map['is_estimated'] = Variable<bool>(isEstimated);
    if (!nullToAbsent || remarks != null) {
      map['remarks'] = Variable<String>(remarks);
    }
    if (!nullToAbsent || imageLocalPath != null) {
      map['image_local_path'] = Variable<String>(imageLocalPath);
    }
    if (!nullToAbsent || imageSecondaryLocalPath != null) {
      map['image_secondary_local_path'] =
          Variable<String>(imageSecondaryLocalPath);
    }
    if (!nullToAbsent || imageAttachmentRemoteId != null) {
      map['image_attachment_remote_id'] =
          Variable<int>(imageAttachmentRemoteId);
    }
    map['sync_status'] = Variable<String>(syncStatus);
    map['sync_attempts'] = Variable<int>(syncAttempts);
    if (!nullToAbsent || syncBatchId != null) {
      map['sync_batch_id'] = Variable<String>(syncBatchId);
    }
    if (!nullToAbsent || lastError != null) {
      map['last_error'] = Variable<String>(lastError);
    }
    map['created_at'] = Variable<DateTime>(createdAt);
    map['updated_at'] = Variable<DateTime>(updatedAt);
    return map;
  }

  ReadingsCompanion toCompanion(bool nullToAbsent) {
    return ReadingsCompanion(
      id: Value(id),
      remoteId: remoteId == null && nullToAbsent
          ? const Value.absent()
          : Value(remoteId),
      meterRemoteId: Value(meterRemoteId),
      readingValue: Value(readingValue),
      readingDate: Value(readingDate),
      capturedPeriodId: capturedPeriodId == null && nullToAbsent
          ? const Value.absent()
          : Value(capturedPeriodId),
      readingCategory: Value(readingCategory),
      isEstimated: Value(isEstimated),
      remarks: remarks == null && nullToAbsent
          ? const Value.absent()
          : Value(remarks),
      imageLocalPath: imageLocalPath == null && nullToAbsent
          ? const Value.absent()
          : Value(imageLocalPath),
      imageSecondaryLocalPath: imageSecondaryLocalPath == null && nullToAbsent
          ? const Value.absent()
          : Value(imageSecondaryLocalPath),
      imageAttachmentRemoteId: imageAttachmentRemoteId == null && nullToAbsent
          ? const Value.absent()
          : Value(imageAttachmentRemoteId),
      syncStatus: Value(syncStatus),
      syncAttempts: Value(syncAttempts),
      syncBatchId: syncBatchId == null && nullToAbsent
          ? const Value.absent()
          : Value(syncBatchId),
      lastError: lastError == null && nullToAbsent
          ? const Value.absent()
          : Value(lastError),
      createdAt: Value(createdAt),
      updatedAt: Value(updatedAt),
    );
  }

  factory Reading.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Reading(
      id: serializer.fromJson<String>(json['id']),
      remoteId: serializer.fromJson<int?>(json['remoteId']),
      meterRemoteId: serializer.fromJson<int>(json['meterRemoteId']),
      readingValue: serializer.fromJson<double>(json['readingValue']),
      readingDate: serializer.fromJson<DateTime>(json['readingDate']),
      capturedPeriodId: serializer.fromJson<int?>(json['capturedPeriodId']),
      readingCategory: serializer.fromJson<String>(json['readingCategory']),
      isEstimated: serializer.fromJson<bool>(json['isEstimated']),
      remarks: serializer.fromJson<String?>(json['remarks']),
      imageLocalPath: serializer.fromJson<String?>(json['imageLocalPath']),
      imageSecondaryLocalPath:
          serializer.fromJson<String?>(json['imageSecondaryLocalPath']),
      imageAttachmentRemoteId:
          serializer.fromJson<int?>(json['imageAttachmentRemoteId']),
      syncStatus: serializer.fromJson<String>(json['syncStatus']),
      syncAttempts: serializer.fromJson<int>(json['syncAttempts']),
      syncBatchId: serializer.fromJson<String?>(json['syncBatchId']),
      lastError: serializer.fromJson<String?>(json['lastError']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      updatedAt: serializer.fromJson<DateTime>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'remoteId': serializer.toJson<int?>(remoteId),
      'meterRemoteId': serializer.toJson<int>(meterRemoteId),
      'readingValue': serializer.toJson<double>(readingValue),
      'readingDate': serializer.toJson<DateTime>(readingDate),
      'capturedPeriodId': serializer.toJson<int?>(capturedPeriodId),
      'readingCategory': serializer.toJson<String>(readingCategory),
      'isEstimated': serializer.toJson<bool>(isEstimated),
      'remarks': serializer.toJson<String?>(remarks),
      'imageLocalPath': serializer.toJson<String?>(imageLocalPath),
      'imageSecondaryLocalPath':
          serializer.toJson<String?>(imageSecondaryLocalPath),
      'imageAttachmentRemoteId':
          serializer.toJson<int?>(imageAttachmentRemoteId),
      'syncStatus': serializer.toJson<String>(syncStatus),
      'syncAttempts': serializer.toJson<int>(syncAttempts),
      'syncBatchId': serializer.toJson<String?>(syncBatchId),
      'lastError': serializer.toJson<String?>(lastError),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'updatedAt': serializer.toJson<DateTime>(updatedAt),
    };
  }

  Reading copyWith(
          {String? id,
          Value<int?> remoteId = const Value.absent(),
          int? meterRemoteId,
          double? readingValue,
          DateTime? readingDate,
          Value<int?> capturedPeriodId = const Value.absent(),
          String? readingCategory,
          bool? isEstimated,
          Value<String?> remarks = const Value.absent(),
          Value<String?> imageLocalPath = const Value.absent(),
          Value<String?> imageSecondaryLocalPath = const Value.absent(),
          Value<int?> imageAttachmentRemoteId = const Value.absent(),
          String? syncStatus,
          int? syncAttempts,
          Value<String?> syncBatchId = const Value.absent(),
          Value<String?> lastError = const Value.absent(),
          DateTime? createdAt,
          DateTime? updatedAt}) =>
      Reading(
        id: id ?? this.id,
        remoteId: remoteId.present ? remoteId.value : this.remoteId,
        meterRemoteId: meterRemoteId ?? this.meterRemoteId,
        readingValue: readingValue ?? this.readingValue,
        readingDate: readingDate ?? this.readingDate,
        capturedPeriodId: capturedPeriodId.present
            ? capturedPeriodId.value
            : this.capturedPeriodId,
        readingCategory: readingCategory ?? this.readingCategory,
        isEstimated: isEstimated ?? this.isEstimated,
        remarks: remarks.present ? remarks.value : this.remarks,
        imageLocalPath:
            imageLocalPath.present ? imageLocalPath.value : this.imageLocalPath,
        imageSecondaryLocalPath: imageSecondaryLocalPath.present
            ? imageSecondaryLocalPath.value
            : this.imageSecondaryLocalPath,
        imageAttachmentRemoteId: imageAttachmentRemoteId.present
            ? imageAttachmentRemoteId.value
            : this.imageAttachmentRemoteId,
        syncStatus: syncStatus ?? this.syncStatus,
        syncAttempts: syncAttempts ?? this.syncAttempts,
        syncBatchId: syncBatchId.present ? syncBatchId.value : this.syncBatchId,
        lastError: lastError.present ? lastError.value : this.lastError,
        createdAt: createdAt ?? this.createdAt,
        updatedAt: updatedAt ?? this.updatedAt,
      );
  Reading copyWithCompanion(ReadingsCompanion data) {
    return Reading(
      id: data.id.present ? data.id.value : this.id,
      remoteId: data.remoteId.present ? data.remoteId.value : this.remoteId,
      meterRemoteId: data.meterRemoteId.present
          ? data.meterRemoteId.value
          : this.meterRemoteId,
      readingValue: data.readingValue.present
          ? data.readingValue.value
          : this.readingValue,
      readingDate:
          data.readingDate.present ? data.readingDate.value : this.readingDate,
      capturedPeriodId: data.capturedPeriodId.present
          ? data.capturedPeriodId.value
          : this.capturedPeriodId,
      readingCategory: data.readingCategory.present
          ? data.readingCategory.value
          : this.readingCategory,
      isEstimated:
          data.isEstimated.present ? data.isEstimated.value : this.isEstimated,
      remarks: data.remarks.present ? data.remarks.value : this.remarks,
      imageLocalPath: data.imageLocalPath.present
          ? data.imageLocalPath.value
          : this.imageLocalPath,
      imageSecondaryLocalPath: data.imageSecondaryLocalPath.present
          ? data.imageSecondaryLocalPath.value
          : this.imageSecondaryLocalPath,
      imageAttachmentRemoteId: data.imageAttachmentRemoteId.present
          ? data.imageAttachmentRemoteId.value
          : this.imageAttachmentRemoteId,
      syncStatus:
          data.syncStatus.present ? data.syncStatus.value : this.syncStatus,
      syncAttempts: data.syncAttempts.present
          ? data.syncAttempts.value
          : this.syncAttempts,
      syncBatchId:
          data.syncBatchId.present ? data.syncBatchId.value : this.syncBatchId,
      lastError: data.lastError.present ? data.lastError.value : this.lastError,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Reading(')
          ..write('id: $id, ')
          ..write('remoteId: $remoteId, ')
          ..write('meterRemoteId: $meterRemoteId, ')
          ..write('readingValue: $readingValue, ')
          ..write('readingDate: $readingDate, ')
          ..write('capturedPeriodId: $capturedPeriodId, ')
          ..write('readingCategory: $readingCategory, ')
          ..write('isEstimated: $isEstimated, ')
          ..write('remarks: $remarks, ')
          ..write('imageLocalPath: $imageLocalPath, ')
          ..write('imageSecondaryLocalPath: $imageSecondaryLocalPath, ')
          ..write('imageAttachmentRemoteId: $imageAttachmentRemoteId, ')
          ..write('syncStatus: $syncStatus, ')
          ..write('syncAttempts: $syncAttempts, ')
          ..write('syncBatchId: $syncBatchId, ')
          ..write('lastError: $lastError, ')
          ..write('createdAt: $createdAt, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
      id,
      remoteId,
      meterRemoteId,
      readingValue,
      readingDate,
      capturedPeriodId,
      readingCategory,
      isEstimated,
      remarks,
      imageLocalPath,
      imageSecondaryLocalPath,
      imageAttachmentRemoteId,
      syncStatus,
      syncAttempts,
      syncBatchId,
      lastError,
      createdAt,
      updatedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Reading &&
          other.id == this.id &&
          other.remoteId == this.remoteId &&
          other.meterRemoteId == this.meterRemoteId &&
          other.readingValue == this.readingValue &&
          other.readingDate == this.readingDate &&
          other.capturedPeriodId == this.capturedPeriodId &&
          other.readingCategory == this.readingCategory &&
          other.isEstimated == this.isEstimated &&
          other.remarks == this.remarks &&
          other.imageLocalPath == this.imageLocalPath &&
          other.imageSecondaryLocalPath == this.imageSecondaryLocalPath &&
          other.imageAttachmentRemoteId == this.imageAttachmentRemoteId &&
          other.syncStatus == this.syncStatus &&
          other.syncAttempts == this.syncAttempts &&
          other.syncBatchId == this.syncBatchId &&
          other.lastError == this.lastError &&
          other.createdAt == this.createdAt &&
          other.updatedAt == this.updatedAt);
}

class ReadingsCompanion extends UpdateCompanion<Reading> {
  final Value<String> id;
  final Value<int?> remoteId;
  final Value<int> meterRemoteId;
  final Value<double> readingValue;
  final Value<DateTime> readingDate;
  final Value<int?> capturedPeriodId;
  final Value<String> readingCategory;
  final Value<bool> isEstimated;
  final Value<String?> remarks;
  final Value<String?> imageLocalPath;
  final Value<String?> imageSecondaryLocalPath;
  final Value<int?> imageAttachmentRemoteId;
  final Value<String> syncStatus;
  final Value<int> syncAttempts;
  final Value<String?> syncBatchId;
  final Value<String?> lastError;
  final Value<DateTime> createdAt;
  final Value<DateTime> updatedAt;
  final Value<int> rowid;
  const ReadingsCompanion({
    this.id = const Value.absent(),
    this.remoteId = const Value.absent(),
    this.meterRemoteId = const Value.absent(),
    this.readingValue = const Value.absent(),
    this.readingDate = const Value.absent(),
    this.capturedPeriodId = const Value.absent(),
    this.readingCategory = const Value.absent(),
    this.isEstimated = const Value.absent(),
    this.remarks = const Value.absent(),
    this.imageLocalPath = const Value.absent(),
    this.imageSecondaryLocalPath = const Value.absent(),
    this.imageAttachmentRemoteId = const Value.absent(),
    this.syncStatus = const Value.absent(),
    this.syncAttempts = const Value.absent(),
    this.syncBatchId = const Value.absent(),
    this.lastError = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ReadingsCompanion.insert({
    required String id,
    this.remoteId = const Value.absent(),
    required int meterRemoteId,
    required double readingValue,
    required DateTime readingDate,
    this.capturedPeriodId = const Value.absent(),
    this.readingCategory = const Value.absent(),
    this.isEstimated = const Value.absent(),
    this.remarks = const Value.absent(),
    this.imageLocalPath = const Value.absent(),
    this.imageSecondaryLocalPath = const Value.absent(),
    this.imageAttachmentRemoteId = const Value.absent(),
    this.syncStatus = const Value.absent(),
    this.syncAttempts = const Value.absent(),
    this.syncBatchId = const Value.absent(),
    this.lastError = const Value.absent(),
    required DateTime createdAt,
    required DateTime updatedAt,
    this.rowid = const Value.absent(),
  })  : id = Value(id),
        meterRemoteId = Value(meterRemoteId),
        readingValue = Value(readingValue),
        readingDate = Value(readingDate),
        createdAt = Value(createdAt),
        updatedAt = Value(updatedAt);
  static Insertable<Reading> custom({
    Expression<String>? id,
    Expression<int>? remoteId,
    Expression<int>? meterRemoteId,
    Expression<double>? readingValue,
    Expression<DateTime>? readingDate,
    Expression<int>? capturedPeriodId,
    Expression<String>? readingCategory,
    Expression<bool>? isEstimated,
    Expression<String>? remarks,
    Expression<String>? imageLocalPath,
    Expression<String>? imageSecondaryLocalPath,
    Expression<int>? imageAttachmentRemoteId,
    Expression<String>? syncStatus,
    Expression<int>? syncAttempts,
    Expression<String>? syncBatchId,
    Expression<String>? lastError,
    Expression<DateTime>? createdAt,
    Expression<DateTime>? updatedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (remoteId != null) 'remote_id': remoteId,
      if (meterRemoteId != null) 'meter_remote_id': meterRemoteId,
      if (readingValue != null) 'reading_value': readingValue,
      if (readingDate != null) 'reading_date': readingDate,
      if (capturedPeriodId != null) 'captured_period_id': capturedPeriodId,
      if (readingCategory != null) 'reading_category': readingCategory,
      if (isEstimated != null) 'is_estimated': isEstimated,
      if (remarks != null) 'remarks': remarks,
      if (imageLocalPath != null) 'image_local_path': imageLocalPath,
      if (imageSecondaryLocalPath != null)
        'image_secondary_local_path': imageSecondaryLocalPath,
      if (imageAttachmentRemoteId != null)
        'image_attachment_remote_id': imageAttachmentRemoteId,
      if (syncStatus != null) 'sync_status': syncStatus,
      if (syncAttempts != null) 'sync_attempts': syncAttempts,
      if (syncBatchId != null) 'sync_batch_id': syncBatchId,
      if (lastError != null) 'last_error': lastError,
      if (createdAt != null) 'created_at': createdAt,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ReadingsCompanion copyWith(
      {Value<String>? id,
      Value<int?>? remoteId,
      Value<int>? meterRemoteId,
      Value<double>? readingValue,
      Value<DateTime>? readingDate,
      Value<int?>? capturedPeriodId,
      Value<String>? readingCategory,
      Value<bool>? isEstimated,
      Value<String?>? remarks,
      Value<String?>? imageLocalPath,
      Value<String?>? imageSecondaryLocalPath,
      Value<int?>? imageAttachmentRemoteId,
      Value<String>? syncStatus,
      Value<int>? syncAttempts,
      Value<String?>? syncBatchId,
      Value<String?>? lastError,
      Value<DateTime>? createdAt,
      Value<DateTime>? updatedAt,
      Value<int>? rowid}) {
    return ReadingsCompanion(
      id: id ?? this.id,
      remoteId: remoteId ?? this.remoteId,
      meterRemoteId: meterRemoteId ?? this.meterRemoteId,
      readingValue: readingValue ?? this.readingValue,
      readingDate: readingDate ?? this.readingDate,
      capturedPeriodId: capturedPeriodId ?? this.capturedPeriodId,
      readingCategory: readingCategory ?? this.readingCategory,
      isEstimated: isEstimated ?? this.isEstimated,
      remarks: remarks ?? this.remarks,
      imageLocalPath: imageLocalPath ?? this.imageLocalPath,
      imageSecondaryLocalPath:
          imageSecondaryLocalPath ?? this.imageSecondaryLocalPath,
      imageAttachmentRemoteId:
          imageAttachmentRemoteId ?? this.imageAttachmentRemoteId,
      syncStatus: syncStatus ?? this.syncStatus,
      syncAttempts: syncAttempts ?? this.syncAttempts,
      syncBatchId: syncBatchId ?? this.syncBatchId,
      lastError: lastError ?? this.lastError,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (remoteId.present) {
      map['remote_id'] = Variable<int>(remoteId.value);
    }
    if (meterRemoteId.present) {
      map['meter_remote_id'] = Variable<int>(meterRemoteId.value);
    }
    if (readingValue.present) {
      map['reading_value'] = Variable<double>(readingValue.value);
    }
    if (readingDate.present) {
      map['reading_date'] = Variable<DateTime>(readingDate.value);
    }
    if (capturedPeriodId.present) {
      map['captured_period_id'] = Variable<int>(capturedPeriodId.value);
    }
    if (readingCategory.present) {
      map['reading_category'] = Variable<String>(readingCategory.value);
    }
    if (isEstimated.present) {
      map['is_estimated'] = Variable<bool>(isEstimated.value);
    }
    if (remarks.present) {
      map['remarks'] = Variable<String>(remarks.value);
    }
    if (imageLocalPath.present) {
      map['image_local_path'] = Variable<String>(imageLocalPath.value);
    }
    if (imageSecondaryLocalPath.present) {
      map['image_secondary_local_path'] =
          Variable<String>(imageSecondaryLocalPath.value);
    }
    if (imageAttachmentRemoteId.present) {
      map['image_attachment_remote_id'] =
          Variable<int>(imageAttachmentRemoteId.value);
    }
    if (syncStatus.present) {
      map['sync_status'] = Variable<String>(syncStatus.value);
    }
    if (syncAttempts.present) {
      map['sync_attempts'] = Variable<int>(syncAttempts.value);
    }
    if (syncBatchId.present) {
      map['sync_batch_id'] = Variable<String>(syncBatchId.value);
    }
    if (lastError.present) {
      map['last_error'] = Variable<String>(lastError.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<DateTime>(updatedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ReadingsCompanion(')
          ..write('id: $id, ')
          ..write('remoteId: $remoteId, ')
          ..write('meterRemoteId: $meterRemoteId, ')
          ..write('readingValue: $readingValue, ')
          ..write('readingDate: $readingDate, ')
          ..write('capturedPeriodId: $capturedPeriodId, ')
          ..write('readingCategory: $readingCategory, ')
          ..write('isEstimated: $isEstimated, ')
          ..write('remarks: $remarks, ')
          ..write('imageLocalPath: $imageLocalPath, ')
          ..write('imageSecondaryLocalPath: $imageSecondaryLocalPath, ')
          ..write('imageAttachmentRemoteId: $imageAttachmentRemoteId, ')
          ..write('syncStatus: $syncStatus, ')
          ..write('syncAttempts: $syncAttempts, ')
          ..write('syncBatchId: $syncBatchId, ')
          ..write('lastError: $lastError, ')
          ..write('createdAt: $createdAt, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $MeterReadingHistoriesTable extends MeterReadingHistories
    with TableInfo<$MeterReadingHistoriesTable, MeterReadingHistory> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MeterReadingHistoriesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _entryKeyMeta =
      const VerificationMeta('entryKey');
  @override
  late final GeneratedColumn<String> entryKey = GeneratedColumn<String>(
      'entry_key', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _meterRemoteIdMeta =
      const VerificationMeta('meterRemoteId');
  @override
  late final GeneratedColumn<int> meterRemoteId = GeneratedColumn<int>(
      'meter_remote_id', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _readingValueMeta =
      const VerificationMeta('readingValue');
  @override
  late final GeneratedColumn<double> readingValue = GeneratedColumn<double>(
      'reading_value', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _readingDateMeta =
      const VerificationMeta('readingDate');
  @override
  late final GeneratedColumn<DateTime> readingDate = GeneratedColumn<DateTime>(
      'reading_date', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  static const VerificationMeta _sourceMeta = const VerificationMeta('source');
  @override
  late final GeneratedColumn<String> source = GeneratedColumn<String>(
      'source', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _syncedAtMeta =
      const VerificationMeta('syncedAt');
  @override
  late final GeneratedColumn<DateTime> syncedAt = GeneratedColumn<DateTime>(
      'synced_at', aliasedName, false,
      type: DriftSqlType.dateTime, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns =>
      [entryKey, meterRemoteId, readingValue, readingDate, source, syncedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'meter_reading_histories';
  @override
  VerificationContext validateIntegrity(
      Insertable<MeterReadingHistory> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('entry_key')) {
      context.handle(_entryKeyMeta,
          entryKey.isAcceptableOrUnknown(data['entry_key']!, _entryKeyMeta));
    } else if (isInserting) {
      context.missing(_entryKeyMeta);
    }
    if (data.containsKey('meter_remote_id')) {
      context.handle(
          _meterRemoteIdMeta,
          meterRemoteId.isAcceptableOrUnknown(
              data['meter_remote_id']!, _meterRemoteIdMeta));
    } else if (isInserting) {
      context.missing(_meterRemoteIdMeta);
    }
    if (data.containsKey('reading_value')) {
      context.handle(
          _readingValueMeta,
          readingValue.isAcceptableOrUnknown(
              data['reading_value']!, _readingValueMeta));
    } else if (isInserting) {
      context.missing(_readingValueMeta);
    }
    if (data.containsKey('reading_date')) {
      context.handle(
          _readingDateMeta,
          readingDate.isAcceptableOrUnknown(
              data['reading_date']!, _readingDateMeta));
    } else if (isInserting) {
      context.missing(_readingDateMeta);
    }
    if (data.containsKey('source')) {
      context.handle(_sourceMeta,
          source.isAcceptableOrUnknown(data['source']!, _sourceMeta));
    } else if (isInserting) {
      context.missing(_sourceMeta);
    }
    if (data.containsKey('synced_at')) {
      context.handle(_syncedAtMeta,
          syncedAt.isAcceptableOrUnknown(data['synced_at']!, _syncedAtMeta));
    } else if (isInserting) {
      context.missing(_syncedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {entryKey};
  @override
  MeterReadingHistory map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return MeterReadingHistory(
      entryKey: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}entry_key'])!,
      meterRemoteId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}meter_remote_id'])!,
      readingValue: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}reading_value'])!,
      readingDate: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}reading_date'])!,
      source: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}source'])!,
      syncedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.dateTime, data['${effectivePrefix}synced_at'])!,
    );
  }

  @override
  $MeterReadingHistoriesTable createAlias(String alias) {
    return $MeterReadingHistoriesTable(attachedDatabase, alias);
  }
}

class MeterReadingHistory extends DataClass
    implements Insertable<MeterReadingHistory> {
  final String entryKey;
  final int meterRemoteId;
  final double readingValue;
  final DateTime readingDate;
  final String source;
  final DateTime syncedAt;
  const MeterReadingHistory(
      {required this.entryKey,
      required this.meterRemoteId,
      required this.readingValue,
      required this.readingDate,
      required this.source,
      required this.syncedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['entry_key'] = Variable<String>(entryKey);
    map['meter_remote_id'] = Variable<int>(meterRemoteId);
    map['reading_value'] = Variable<double>(readingValue);
    map['reading_date'] = Variable<DateTime>(readingDate);
    map['source'] = Variable<String>(source);
    map['synced_at'] = Variable<DateTime>(syncedAt);
    return map;
  }

  MeterReadingHistoriesCompanion toCompanion(bool nullToAbsent) {
    return MeterReadingHistoriesCompanion(
      entryKey: Value(entryKey),
      meterRemoteId: Value(meterRemoteId),
      readingValue: Value(readingValue),
      readingDate: Value(readingDate),
      source: Value(source),
      syncedAt: Value(syncedAt),
    );
  }

  factory MeterReadingHistory.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return MeterReadingHistory(
      entryKey: serializer.fromJson<String>(json['entryKey']),
      meterRemoteId: serializer.fromJson<int>(json['meterRemoteId']),
      readingValue: serializer.fromJson<double>(json['readingValue']),
      readingDate: serializer.fromJson<DateTime>(json['readingDate']),
      source: serializer.fromJson<String>(json['source']),
      syncedAt: serializer.fromJson<DateTime>(json['syncedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'entryKey': serializer.toJson<String>(entryKey),
      'meterRemoteId': serializer.toJson<int>(meterRemoteId),
      'readingValue': serializer.toJson<double>(readingValue),
      'readingDate': serializer.toJson<DateTime>(readingDate),
      'source': serializer.toJson<String>(source),
      'syncedAt': serializer.toJson<DateTime>(syncedAt),
    };
  }

  MeterReadingHistory copyWith(
          {String? entryKey,
          int? meterRemoteId,
          double? readingValue,
          DateTime? readingDate,
          String? source,
          DateTime? syncedAt}) =>
      MeterReadingHistory(
        entryKey: entryKey ?? this.entryKey,
        meterRemoteId: meterRemoteId ?? this.meterRemoteId,
        readingValue: readingValue ?? this.readingValue,
        readingDate: readingDate ?? this.readingDate,
        source: source ?? this.source,
        syncedAt: syncedAt ?? this.syncedAt,
      );
  MeterReadingHistory copyWithCompanion(MeterReadingHistoriesCompanion data) {
    return MeterReadingHistory(
      entryKey: data.entryKey.present ? data.entryKey.value : this.entryKey,
      meterRemoteId: data.meterRemoteId.present
          ? data.meterRemoteId.value
          : this.meterRemoteId,
      readingValue: data.readingValue.present
          ? data.readingValue.value
          : this.readingValue,
      readingDate:
          data.readingDate.present ? data.readingDate.value : this.readingDate,
      source: data.source.present ? data.source.value : this.source,
      syncedAt: data.syncedAt.present ? data.syncedAt.value : this.syncedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('MeterReadingHistory(')
          ..write('entryKey: $entryKey, ')
          ..write('meterRemoteId: $meterRemoteId, ')
          ..write('readingValue: $readingValue, ')
          ..write('readingDate: $readingDate, ')
          ..write('source: $source, ')
          ..write('syncedAt: $syncedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
      entryKey, meterRemoteId, readingValue, readingDate, source, syncedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is MeterReadingHistory &&
          other.entryKey == this.entryKey &&
          other.meterRemoteId == this.meterRemoteId &&
          other.readingValue == this.readingValue &&
          other.readingDate == this.readingDate &&
          other.source == this.source &&
          other.syncedAt == this.syncedAt);
}

class MeterReadingHistoriesCompanion
    extends UpdateCompanion<MeterReadingHistory> {
  final Value<String> entryKey;
  final Value<int> meterRemoteId;
  final Value<double> readingValue;
  final Value<DateTime> readingDate;
  final Value<String> source;
  final Value<DateTime> syncedAt;
  final Value<int> rowid;
  const MeterReadingHistoriesCompanion({
    this.entryKey = const Value.absent(),
    this.meterRemoteId = const Value.absent(),
    this.readingValue = const Value.absent(),
    this.readingDate = const Value.absent(),
    this.source = const Value.absent(),
    this.syncedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  MeterReadingHistoriesCompanion.insert({
    required String entryKey,
    required int meterRemoteId,
    required double readingValue,
    required DateTime readingDate,
    required String source,
    required DateTime syncedAt,
    this.rowid = const Value.absent(),
  })  : entryKey = Value(entryKey),
        meterRemoteId = Value(meterRemoteId),
        readingValue = Value(readingValue),
        readingDate = Value(readingDate),
        source = Value(source),
        syncedAt = Value(syncedAt);
  static Insertable<MeterReadingHistory> custom({
    Expression<String>? entryKey,
    Expression<int>? meterRemoteId,
    Expression<double>? readingValue,
    Expression<DateTime>? readingDate,
    Expression<String>? source,
    Expression<DateTime>? syncedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (entryKey != null) 'entry_key': entryKey,
      if (meterRemoteId != null) 'meter_remote_id': meterRemoteId,
      if (readingValue != null) 'reading_value': readingValue,
      if (readingDate != null) 'reading_date': readingDate,
      if (source != null) 'source': source,
      if (syncedAt != null) 'synced_at': syncedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  MeterReadingHistoriesCompanion copyWith(
      {Value<String>? entryKey,
      Value<int>? meterRemoteId,
      Value<double>? readingValue,
      Value<DateTime>? readingDate,
      Value<String>? source,
      Value<DateTime>? syncedAt,
      Value<int>? rowid}) {
    return MeterReadingHistoriesCompanion(
      entryKey: entryKey ?? this.entryKey,
      meterRemoteId: meterRemoteId ?? this.meterRemoteId,
      readingValue: readingValue ?? this.readingValue,
      readingDate: readingDate ?? this.readingDate,
      source: source ?? this.source,
      syncedAt: syncedAt ?? this.syncedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (entryKey.present) {
      map['entry_key'] = Variable<String>(entryKey.value);
    }
    if (meterRemoteId.present) {
      map['meter_remote_id'] = Variable<int>(meterRemoteId.value);
    }
    if (readingValue.present) {
      map['reading_value'] = Variable<double>(readingValue.value);
    }
    if (readingDate.present) {
      map['reading_date'] = Variable<DateTime>(readingDate.value);
    }
    if (source.present) {
      map['source'] = Variable<String>(source.value);
    }
    if (syncedAt.present) {
      map['synced_at'] = Variable<DateTime>(syncedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MeterReadingHistoriesCompanion(')
          ..write('entryKey: $entryKey, ')
          ..write('meterRemoteId: $meterRemoteId, ')
          ..write('readingValue: $readingValue, ')
          ..write('readingDate: $readingDate, ')
          ..write('source: $source, ')
          ..write('syncedAt: $syncedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $CustomersTable customers = $CustomersTable(this);
  late final $MetersTable meters = $MetersTable(this);
  late final $AssignmentsTable assignments = $AssignmentsTable(this);
  late final $PeriodsTable periods = $PeriodsTable(this);
  late final $SyncBatchesTable syncBatches = $SyncBatchesTable(this);
  late final $ReadingsTable readings = $ReadingsTable(this);
  late final $MeterReadingHistoriesTable meterReadingHistories =
      $MeterReadingHistoriesTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
        customers,
        meters,
        assignments,
        periods,
        syncBatches,
        readings,
        meterReadingHistories
      ];
}

typedef $$CustomersTableCreateCompanionBuilder = CustomersCompanion Function({
  Value<int> remoteId,
  required String accountNumber,
  required String name,
  Value<String?> address,
  Value<int?> routeId,
  Value<DateTime?> lastReadingDate,
  Value<double?> lastReadingValue,
  required DateTime lastSyncedAt,
});
typedef $$CustomersTableUpdateCompanionBuilder = CustomersCompanion Function({
  Value<int> remoteId,
  Value<String> accountNumber,
  Value<String> name,
  Value<String?> address,
  Value<int?> routeId,
  Value<DateTime?> lastReadingDate,
  Value<double?> lastReadingValue,
  Value<DateTime> lastSyncedAt,
});

final class $$CustomersTableReferences
    extends BaseReferences<_$AppDatabase, $CustomersTable, Customer> {
  $$CustomersTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static MultiTypedResultKey<$MetersTable, List<Meter>> _metersRefsTable(
          _$AppDatabase db) =>
      MultiTypedResultKey.fromTable(db.meters,
          aliasName: $_aliasNameGenerator(
              db.customers.remoteId, db.meters.customerRemoteId));

  $$MetersTableProcessedTableManager get metersRefs {
    final manager = $$MetersTableTableManager($_db, $_db.meters).filter((f) =>
        f.customerRemoteId.remoteId.sqlEquals($_itemColumn<int>('remote_id')!));

    final cache = $_typedResult.readTableOrNull(_metersRefsTable($_db));
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: cache));
  }
}

class $$CustomersTableFilterComposer
    extends Composer<_$AppDatabase, $CustomersTable> {
  $$CustomersTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get remoteId => $composableBuilder(
      column: $table.remoteId, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get accountNumber => $composableBuilder(
      column: $table.accountNumber, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get name => $composableBuilder(
      column: $table.name, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get address => $composableBuilder(
      column: $table.address, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get routeId => $composableBuilder(
      column: $table.routeId, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get lastReadingDate => $composableBuilder(
      column: $table.lastReadingDate,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get lastReadingValue => $composableBuilder(
      column: $table.lastReadingValue,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get lastSyncedAt => $composableBuilder(
      column: $table.lastSyncedAt, builder: (column) => ColumnFilters(column));

  Expression<bool> metersRefs(
      Expression<bool> Function($$MetersTableFilterComposer f) f) {
    final $$MetersTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.remoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.customerRemoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableFilterComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$CustomersTableOrderingComposer
    extends Composer<_$AppDatabase, $CustomersTable> {
  $$CustomersTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get remoteId => $composableBuilder(
      column: $table.remoteId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get accountNumber => $composableBuilder(
      column: $table.accountNumber,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get name => $composableBuilder(
      column: $table.name, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get address => $composableBuilder(
      column: $table.address, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get routeId => $composableBuilder(
      column: $table.routeId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get lastReadingDate => $composableBuilder(
      column: $table.lastReadingDate,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get lastReadingValue => $composableBuilder(
      column: $table.lastReadingValue,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get lastSyncedAt => $composableBuilder(
      column: $table.lastSyncedAt,
      builder: (column) => ColumnOrderings(column));
}

class $$CustomersTableAnnotationComposer
    extends Composer<_$AppDatabase, $CustomersTable> {
  $$CustomersTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get remoteId =>
      $composableBuilder(column: $table.remoteId, builder: (column) => column);

  GeneratedColumn<String> get accountNumber => $composableBuilder(
      column: $table.accountNumber, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<String> get address =>
      $composableBuilder(column: $table.address, builder: (column) => column);

  GeneratedColumn<int> get routeId =>
      $composableBuilder(column: $table.routeId, builder: (column) => column);

  GeneratedColumn<DateTime> get lastReadingDate => $composableBuilder(
      column: $table.lastReadingDate, builder: (column) => column);

  GeneratedColumn<double> get lastReadingValue => $composableBuilder(
      column: $table.lastReadingValue, builder: (column) => column);

  GeneratedColumn<DateTime> get lastSyncedAt => $composableBuilder(
      column: $table.lastSyncedAt, builder: (column) => column);

  Expression<T> metersRefs<T extends Object>(
      Expression<T> Function($$MetersTableAnnotationComposer a) f) {
    final $$MetersTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.remoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.customerRemoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableAnnotationComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$CustomersTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CustomersTable,
    Customer,
    $$CustomersTableFilterComposer,
    $$CustomersTableOrderingComposer,
    $$CustomersTableAnnotationComposer,
    $$CustomersTableCreateCompanionBuilder,
    $$CustomersTableUpdateCompanionBuilder,
    (Customer, $$CustomersTableReferences),
    Customer,
    PrefetchHooks Function({bool metersRefs})> {
  $$CustomersTableTableManager(_$AppDatabase db, $CustomersTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CustomersTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CustomersTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CustomersTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> remoteId = const Value.absent(),
            Value<String> accountNumber = const Value.absent(),
            Value<String> name = const Value.absent(),
            Value<String?> address = const Value.absent(),
            Value<int?> routeId = const Value.absent(),
            Value<DateTime?> lastReadingDate = const Value.absent(),
            Value<double?> lastReadingValue = const Value.absent(),
            Value<DateTime> lastSyncedAt = const Value.absent(),
          }) =>
              CustomersCompanion(
            remoteId: remoteId,
            accountNumber: accountNumber,
            name: name,
            address: address,
            routeId: routeId,
            lastReadingDate: lastReadingDate,
            lastReadingValue: lastReadingValue,
            lastSyncedAt: lastSyncedAt,
          ),
          createCompanionCallback: ({
            Value<int> remoteId = const Value.absent(),
            required String accountNumber,
            required String name,
            Value<String?> address = const Value.absent(),
            Value<int?> routeId = const Value.absent(),
            Value<DateTime?> lastReadingDate = const Value.absent(),
            Value<double?> lastReadingValue = const Value.absent(),
            required DateTime lastSyncedAt,
          }) =>
              CustomersCompanion.insert(
            remoteId: remoteId,
            accountNumber: accountNumber,
            name: name,
            address: address,
            routeId: routeId,
            lastReadingDate: lastReadingDate,
            lastReadingValue: lastReadingValue,
            lastSyncedAt: lastSyncedAt,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (
                    e.readTable(table),
                    $$CustomersTableReferences(db, table, e)
                  ))
              .toList(),
          prefetchHooksCallback: ({metersRefs = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [if (metersRefs) db.meters],
              addJoins: null,
              getPrefetchedDataCallback: (items) async {
                return [
                  if (metersRefs)
                    await $_getPrefetchedData<Customer, $CustomersTable, Meter>(
                        currentTable: table,
                        referencedTable:
                            $$CustomersTableReferences._metersRefsTable(db),
                        managerFromTypedResult: (p0) =>
                            $$CustomersTableReferences(db, table, p0)
                                .metersRefs,
                        referencedItemsForCurrentItem:
                            (item, referencedItems) => referencedItems.where(
                                (e) => e.customerRemoteId == item.remoteId),
                        typedResults: items)
                ];
              },
            );
          },
        ));
}

typedef $$CustomersTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CustomersTable,
    Customer,
    $$CustomersTableFilterComposer,
    $$CustomersTableOrderingComposer,
    $$CustomersTableAnnotationComposer,
    $$CustomersTableCreateCompanionBuilder,
    $$CustomersTableUpdateCompanionBuilder,
    (Customer, $$CustomersTableReferences),
    Customer,
    PrefetchHooks Function({bool metersRefs})>;
typedef $$MetersTableCreateCompanionBuilder = MetersCompanion Function({
  Value<int> remoteId,
  required String meterNumber,
  Value<String?> serialNumber,
  required int customerRemoteId,
  Value<String?> meterType,
  required String paymentType,
  Value<String?> communicationType,
  Value<int?> routeId,
  Value<bool> isCouplingMeter,
});
typedef $$MetersTableUpdateCompanionBuilder = MetersCompanion Function({
  Value<int> remoteId,
  Value<String> meterNumber,
  Value<String?> serialNumber,
  Value<int> customerRemoteId,
  Value<String?> meterType,
  Value<String> paymentType,
  Value<String?> communicationType,
  Value<int?> routeId,
  Value<bool> isCouplingMeter,
});

final class $$MetersTableReferences
    extends BaseReferences<_$AppDatabase, $MetersTable, Meter> {
  $$MetersTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $CustomersTable _customerRemoteIdTable(_$AppDatabase db) =>
      db.customers.createAlias($_aliasNameGenerator(
          db.meters.customerRemoteId, db.customers.remoteId));

  $$CustomersTableProcessedTableManager get customerRemoteId {
    final $_column = $_itemColumn<int>('customer_remote_id')!;

    final manager = $$CustomersTableTableManager($_db, $_db.customers)
        .filter((f) => f.remoteId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_customerRemoteIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: [item]));
  }

  static MultiTypedResultKey<$AssignmentsTable, List<Assignment>>
      _assignmentsRefsTable(_$AppDatabase db) =>
          MultiTypedResultKey.fromTable(db.assignments,
              aliasName: $_aliasNameGenerator(
                  db.meters.remoteId, db.assignments.meterRemoteId));

  $$AssignmentsTableProcessedTableManager get assignmentsRefs {
    final manager = $$AssignmentsTableTableManager($_db, $_db.assignments)
        .filter((f) => f.meterRemoteId.remoteId
            .sqlEquals($_itemColumn<int>('remote_id')!));

    final cache = $_typedResult.readTableOrNull(_assignmentsRefsTable($_db));
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: cache));
  }

  static MultiTypedResultKey<$ReadingsTable, List<Reading>> _readingsRefsTable(
          _$AppDatabase db) =>
      MultiTypedResultKey.fromTable(db.readings,
          aliasName: $_aliasNameGenerator(
              db.meters.remoteId, db.readings.meterRemoteId));

  $$ReadingsTableProcessedTableManager get readingsRefs {
    final manager = $$ReadingsTableTableManager($_db, $_db.readings).filter(
        (f) => f.meterRemoteId.remoteId
            .sqlEquals($_itemColumn<int>('remote_id')!));

    final cache = $_typedResult.readTableOrNull(_readingsRefsTable($_db));
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: cache));
  }
}

class $$MetersTableFilterComposer
    extends Composer<_$AppDatabase, $MetersTable> {
  $$MetersTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get remoteId => $composableBuilder(
      column: $table.remoteId, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get meterNumber => $composableBuilder(
      column: $table.meterNumber, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get serialNumber => $composableBuilder(
      column: $table.serialNumber, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get meterType => $composableBuilder(
      column: $table.meterType, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get paymentType => $composableBuilder(
      column: $table.paymentType, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get communicationType => $composableBuilder(
      column: $table.communicationType,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get routeId => $composableBuilder(
      column: $table.routeId, builder: (column) => ColumnFilters(column));

  ColumnFilters<bool> get isCouplingMeter => $composableBuilder(
      column: $table.isCouplingMeter,
      builder: (column) => ColumnFilters(column));

  $$CustomersTableFilterComposer get customerRemoteId {
    final $$CustomersTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.customerRemoteId,
        referencedTable: $db.customers,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$CustomersTableFilterComposer(
              $db: $db,
              $table: $db.customers,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }

  Expression<bool> assignmentsRefs(
      Expression<bool> Function($$AssignmentsTableFilterComposer f) f) {
    final $$AssignmentsTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.remoteId,
        referencedTable: $db.assignments,
        getReferencedColumn: (t) => t.meterRemoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$AssignmentsTableFilterComposer(
              $db: $db,
              $table: $db.assignments,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }

  Expression<bool> readingsRefs(
      Expression<bool> Function($$ReadingsTableFilterComposer f) f) {
    final $$ReadingsTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.remoteId,
        referencedTable: $db.readings,
        getReferencedColumn: (t) => t.meterRemoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$ReadingsTableFilterComposer(
              $db: $db,
              $table: $db.readings,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$MetersTableOrderingComposer
    extends Composer<_$AppDatabase, $MetersTable> {
  $$MetersTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get remoteId => $composableBuilder(
      column: $table.remoteId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get meterNumber => $composableBuilder(
      column: $table.meterNumber, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get serialNumber => $composableBuilder(
      column: $table.serialNumber,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get meterType => $composableBuilder(
      column: $table.meterType, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get paymentType => $composableBuilder(
      column: $table.paymentType, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get communicationType => $composableBuilder(
      column: $table.communicationType,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get routeId => $composableBuilder(
      column: $table.routeId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<bool> get isCouplingMeter => $composableBuilder(
      column: $table.isCouplingMeter,
      builder: (column) => ColumnOrderings(column));

  $$CustomersTableOrderingComposer get customerRemoteId {
    final $$CustomersTableOrderingComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.customerRemoteId,
        referencedTable: $db.customers,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$CustomersTableOrderingComposer(
              $db: $db,
              $table: $db.customers,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$MetersTableAnnotationComposer
    extends Composer<_$AppDatabase, $MetersTable> {
  $$MetersTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get remoteId =>
      $composableBuilder(column: $table.remoteId, builder: (column) => column);

  GeneratedColumn<String> get meterNumber => $composableBuilder(
      column: $table.meterNumber, builder: (column) => column);

  GeneratedColumn<String> get serialNumber => $composableBuilder(
      column: $table.serialNumber, builder: (column) => column);

  GeneratedColumn<String> get meterType =>
      $composableBuilder(column: $table.meterType, builder: (column) => column);

  GeneratedColumn<String> get paymentType => $composableBuilder(
      column: $table.paymentType, builder: (column) => column);

  GeneratedColumn<String> get communicationType => $composableBuilder(
      column: $table.communicationType, builder: (column) => column);

  GeneratedColumn<int> get routeId =>
      $composableBuilder(column: $table.routeId, builder: (column) => column);

  GeneratedColumn<bool> get isCouplingMeter => $composableBuilder(
      column: $table.isCouplingMeter, builder: (column) => column);

  $$CustomersTableAnnotationComposer get customerRemoteId {
    final $$CustomersTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.customerRemoteId,
        referencedTable: $db.customers,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$CustomersTableAnnotationComposer(
              $db: $db,
              $table: $db.customers,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }

  Expression<T> assignmentsRefs<T extends Object>(
      Expression<T> Function($$AssignmentsTableAnnotationComposer a) f) {
    final $$AssignmentsTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.remoteId,
        referencedTable: $db.assignments,
        getReferencedColumn: (t) => t.meterRemoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$AssignmentsTableAnnotationComposer(
              $db: $db,
              $table: $db.assignments,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }

  Expression<T> readingsRefs<T extends Object>(
      Expression<T> Function($$ReadingsTableAnnotationComposer a) f) {
    final $$ReadingsTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.remoteId,
        referencedTable: $db.readings,
        getReferencedColumn: (t) => t.meterRemoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$ReadingsTableAnnotationComposer(
              $db: $db,
              $table: $db.readings,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$MetersTableTableManager extends RootTableManager<
    _$AppDatabase,
    $MetersTable,
    Meter,
    $$MetersTableFilterComposer,
    $$MetersTableOrderingComposer,
    $$MetersTableAnnotationComposer,
    $$MetersTableCreateCompanionBuilder,
    $$MetersTableUpdateCompanionBuilder,
    (Meter, $$MetersTableReferences),
    Meter,
    PrefetchHooks Function(
        {bool customerRemoteId, bool assignmentsRefs, bool readingsRefs})> {
  $$MetersTableTableManager(_$AppDatabase db, $MetersTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MetersTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$MetersTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MetersTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> remoteId = const Value.absent(),
            Value<String> meterNumber = const Value.absent(),
            Value<String?> serialNumber = const Value.absent(),
            Value<int> customerRemoteId = const Value.absent(),
            Value<String?> meterType = const Value.absent(),
            Value<String> paymentType = const Value.absent(),
            Value<String?> communicationType = const Value.absent(),
            Value<int?> routeId = const Value.absent(),
            Value<bool> isCouplingMeter = const Value.absent(),
          }) =>
              MetersCompanion(
            remoteId: remoteId,
            meterNumber: meterNumber,
            serialNumber: serialNumber,
            customerRemoteId: customerRemoteId,
            meterType: meterType,
            paymentType: paymentType,
            communicationType: communicationType,
            routeId: routeId,
            isCouplingMeter: isCouplingMeter,
          ),
          createCompanionCallback: ({
            Value<int> remoteId = const Value.absent(),
            required String meterNumber,
            Value<String?> serialNumber = const Value.absent(),
            required int customerRemoteId,
            Value<String?> meterType = const Value.absent(),
            required String paymentType,
            Value<String?> communicationType = const Value.absent(),
            Value<int?> routeId = const Value.absent(),
            Value<bool> isCouplingMeter = const Value.absent(),
          }) =>
              MetersCompanion.insert(
            remoteId: remoteId,
            meterNumber: meterNumber,
            serialNumber: serialNumber,
            customerRemoteId: customerRemoteId,
            meterType: meterType,
            paymentType: paymentType,
            communicationType: communicationType,
            routeId: routeId,
            isCouplingMeter: isCouplingMeter,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) =>
                  (e.readTable(table), $$MetersTableReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: (
              {customerRemoteId = false,
              assignmentsRefs = false,
              readingsRefs = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [
                if (assignmentsRefs) db.assignments,
                if (readingsRefs) db.readings
              ],
              addJoins: <
                  T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic>>(state) {
                if (customerRemoteId) {
                  state = state.withJoin(
                    currentTable: table,
                    currentColumn: table.customerRemoteId,
                    referencedTable:
                        $$MetersTableReferences._customerRemoteIdTable(db),
                    referencedColumn: $$MetersTableReferences
                        ._customerRemoteIdTable(db)
                        .remoteId,
                  ) as T;
                }

                return state;
              },
              getPrefetchedDataCallback: (items) async {
                return [
                  if (assignmentsRefs)
                    await $_getPrefetchedData<Meter, $MetersTable, Assignment>(
                        currentTable: table,
                        referencedTable:
                            $$MetersTableReferences._assignmentsRefsTable(db),
                        managerFromTypedResult: (p0) =>
                            $$MetersTableReferences(db, table, p0)
                                .assignmentsRefs,
                        referencedItemsForCurrentItem:
                            (item, referencedItems) => referencedItems
                                .where((e) => e.meterRemoteId == item.remoteId),
                        typedResults: items),
                  if (readingsRefs)
                    await $_getPrefetchedData<Meter, $MetersTable, Reading>(
                        currentTable: table,
                        referencedTable:
                            $$MetersTableReferences._readingsRefsTable(db),
                        managerFromTypedResult: (p0) =>
                            $$MetersTableReferences(db, table, p0).readingsRefs,
                        referencedItemsForCurrentItem:
                            (item, referencedItems) => referencedItems
                                .where((e) => e.meterRemoteId == item.remoteId),
                        typedResults: items)
                ];
              },
            );
          },
        ));
}

typedef $$MetersTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $MetersTable,
    Meter,
    $$MetersTableFilterComposer,
    $$MetersTableOrderingComposer,
    $$MetersTableAnnotationComposer,
    $$MetersTableCreateCompanionBuilder,
    $$MetersTableUpdateCompanionBuilder,
    (Meter, $$MetersTableReferences),
    Meter,
    PrefetchHooks Function(
        {bool customerRemoteId, bool assignmentsRefs, bool readingsRefs})>;
typedef $$AssignmentsTableCreateCompanionBuilder = AssignmentsCompanion
    Function({
  required String id,
  required int meterRemoteId,
  required int periodId,
  Value<String> status,
  required DateTime downloadedAt,
  Value<int> rowid,
});
typedef $$AssignmentsTableUpdateCompanionBuilder = AssignmentsCompanion
    Function({
  Value<String> id,
  Value<int> meterRemoteId,
  Value<int> periodId,
  Value<String> status,
  Value<DateTime> downloadedAt,
  Value<int> rowid,
});

final class $$AssignmentsTableReferences
    extends BaseReferences<_$AppDatabase, $AssignmentsTable, Assignment> {
  $$AssignmentsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $MetersTable _meterRemoteIdTable(_$AppDatabase db) =>
      db.meters.createAlias($_aliasNameGenerator(
          db.assignments.meterRemoteId, db.meters.remoteId));

  $$MetersTableProcessedTableManager get meterRemoteId {
    final $_column = $_itemColumn<int>('meter_remote_id')!;

    final manager = $$MetersTableTableManager($_db, $_db.meters)
        .filter((f) => f.remoteId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_meterRemoteIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: [item]));
  }
}

class $$AssignmentsTableFilterComposer
    extends Composer<_$AppDatabase, $AssignmentsTable> {
  $$AssignmentsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get periodId => $composableBuilder(
      column: $table.periodId, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get status => $composableBuilder(
      column: $table.status, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get downloadedAt => $composableBuilder(
      column: $table.downloadedAt, builder: (column) => ColumnFilters(column));

  $$MetersTableFilterComposer get meterRemoteId {
    final $$MetersTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.meterRemoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableFilterComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$AssignmentsTableOrderingComposer
    extends Composer<_$AppDatabase, $AssignmentsTable> {
  $$AssignmentsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get periodId => $composableBuilder(
      column: $table.periodId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get status => $composableBuilder(
      column: $table.status, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get downloadedAt => $composableBuilder(
      column: $table.downloadedAt,
      builder: (column) => ColumnOrderings(column));

  $$MetersTableOrderingComposer get meterRemoteId {
    final $$MetersTableOrderingComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.meterRemoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableOrderingComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$AssignmentsTableAnnotationComposer
    extends Composer<_$AppDatabase, $AssignmentsTable> {
  $$AssignmentsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<int> get periodId =>
      $composableBuilder(column: $table.periodId, builder: (column) => column);

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<DateTime> get downloadedAt => $composableBuilder(
      column: $table.downloadedAt, builder: (column) => column);

  $$MetersTableAnnotationComposer get meterRemoteId {
    final $$MetersTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.meterRemoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableAnnotationComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$AssignmentsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $AssignmentsTable,
    Assignment,
    $$AssignmentsTableFilterComposer,
    $$AssignmentsTableOrderingComposer,
    $$AssignmentsTableAnnotationComposer,
    $$AssignmentsTableCreateCompanionBuilder,
    $$AssignmentsTableUpdateCompanionBuilder,
    (Assignment, $$AssignmentsTableReferences),
    Assignment,
    PrefetchHooks Function({bool meterRemoteId})> {
  $$AssignmentsTableTableManager(_$AppDatabase db, $AssignmentsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$AssignmentsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$AssignmentsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$AssignmentsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> id = const Value.absent(),
            Value<int> meterRemoteId = const Value.absent(),
            Value<int> periodId = const Value.absent(),
            Value<String> status = const Value.absent(),
            Value<DateTime> downloadedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              AssignmentsCompanion(
            id: id,
            meterRemoteId: meterRemoteId,
            periodId: periodId,
            status: status,
            downloadedAt: downloadedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String id,
            required int meterRemoteId,
            required int periodId,
            Value<String> status = const Value.absent(),
            required DateTime downloadedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              AssignmentsCompanion.insert(
            id: id,
            meterRemoteId: meterRemoteId,
            periodId: periodId,
            status: status,
            downloadedAt: downloadedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (
                    e.readTable(table),
                    $$AssignmentsTableReferences(db, table, e)
                  ))
              .toList(),
          prefetchHooksCallback: ({meterRemoteId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins: <
                  T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic>>(state) {
                if (meterRemoteId) {
                  state = state.withJoin(
                    currentTable: table,
                    currentColumn: table.meterRemoteId,
                    referencedTable:
                        $$AssignmentsTableReferences._meterRemoteIdTable(db),
                    referencedColumn: $$AssignmentsTableReferences
                        ._meterRemoteIdTable(db)
                        .remoteId,
                  ) as T;
                }

                return state;
              },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ));
}

typedef $$AssignmentsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $AssignmentsTable,
    Assignment,
    $$AssignmentsTableFilterComposer,
    $$AssignmentsTableOrderingComposer,
    $$AssignmentsTableAnnotationComposer,
    $$AssignmentsTableCreateCompanionBuilder,
    $$AssignmentsTableUpdateCompanionBuilder,
    (Assignment, $$AssignmentsTableReferences),
    Assignment,
    PrefetchHooks Function({bool meterRemoteId})>;
typedef $$PeriodsTableCreateCompanionBuilder = PeriodsCompanion Function({
  Value<int> id,
  required String name,
  Value<DateTime?> dateStart,
  Value<DateTime?> dateEnd,
  Value<bool> isCurrent,
});
typedef $$PeriodsTableUpdateCompanionBuilder = PeriodsCompanion Function({
  Value<int> id,
  Value<String> name,
  Value<DateTime?> dateStart,
  Value<DateTime?> dateEnd,
  Value<bool> isCurrent,
});

class $$PeriodsTableFilterComposer
    extends Composer<_$AppDatabase, $PeriodsTable> {
  $$PeriodsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get name => $composableBuilder(
      column: $table.name, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get dateStart => $composableBuilder(
      column: $table.dateStart, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get dateEnd => $composableBuilder(
      column: $table.dateEnd, builder: (column) => ColumnFilters(column));

  ColumnFilters<bool> get isCurrent => $composableBuilder(
      column: $table.isCurrent, builder: (column) => ColumnFilters(column));
}

class $$PeriodsTableOrderingComposer
    extends Composer<_$AppDatabase, $PeriodsTable> {
  $$PeriodsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get name => $composableBuilder(
      column: $table.name, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get dateStart => $composableBuilder(
      column: $table.dateStart, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get dateEnd => $composableBuilder(
      column: $table.dateEnd, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<bool> get isCurrent => $composableBuilder(
      column: $table.isCurrent, builder: (column) => ColumnOrderings(column));
}

class $$PeriodsTableAnnotationComposer
    extends Composer<_$AppDatabase, $PeriodsTable> {
  $$PeriodsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<DateTime> get dateStart =>
      $composableBuilder(column: $table.dateStart, builder: (column) => column);

  GeneratedColumn<DateTime> get dateEnd =>
      $composableBuilder(column: $table.dateEnd, builder: (column) => column);

  GeneratedColumn<bool> get isCurrent =>
      $composableBuilder(column: $table.isCurrent, builder: (column) => column);
}

class $$PeriodsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $PeriodsTable,
    Period,
    $$PeriodsTableFilterComposer,
    $$PeriodsTableOrderingComposer,
    $$PeriodsTableAnnotationComposer,
    $$PeriodsTableCreateCompanionBuilder,
    $$PeriodsTableUpdateCompanionBuilder,
    (Period, BaseReferences<_$AppDatabase, $PeriodsTable, Period>),
    Period,
    PrefetchHooks Function()> {
  $$PeriodsTableTableManager(_$AppDatabase db, $PeriodsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$PeriodsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$PeriodsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$PeriodsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> id = const Value.absent(),
            Value<String> name = const Value.absent(),
            Value<DateTime?> dateStart = const Value.absent(),
            Value<DateTime?> dateEnd = const Value.absent(),
            Value<bool> isCurrent = const Value.absent(),
          }) =>
              PeriodsCompanion(
            id: id,
            name: name,
            dateStart: dateStart,
            dateEnd: dateEnd,
            isCurrent: isCurrent,
          ),
          createCompanionCallback: ({
            Value<int> id = const Value.absent(),
            required String name,
            Value<DateTime?> dateStart = const Value.absent(),
            Value<DateTime?> dateEnd = const Value.absent(),
            Value<bool> isCurrent = const Value.absent(),
          }) =>
              PeriodsCompanion.insert(
            id: id,
            name: name,
            dateStart: dateStart,
            dateEnd: dateEnd,
            isCurrent: isCurrent,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$PeriodsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $PeriodsTable,
    Period,
    $$PeriodsTableFilterComposer,
    $$PeriodsTableOrderingComposer,
    $$PeriodsTableAnnotationComposer,
    $$PeriodsTableCreateCompanionBuilder,
    $$PeriodsTableUpdateCompanionBuilder,
    (Period, BaseReferences<_$AppDatabase, $PeriodsTable, Period>),
    Period,
    PrefetchHooks Function()>;
typedef $$SyncBatchesTableCreateCompanionBuilder = SyncBatchesCompanion
    Function({
  required String id,
  Value<String> status,
  Value<String?> archivePath,
  required int readingCount,
  Value<int> retryCount,
  Value<String?> lastError,
  required DateTime createdAt,
  Value<DateTime?> lastAttemptAt,
  Value<int> rowid,
});
typedef $$SyncBatchesTableUpdateCompanionBuilder = SyncBatchesCompanion
    Function({
  Value<String> id,
  Value<String> status,
  Value<String?> archivePath,
  Value<int> readingCount,
  Value<int> retryCount,
  Value<String?> lastError,
  Value<DateTime> createdAt,
  Value<DateTime?> lastAttemptAt,
  Value<int> rowid,
});

final class $$SyncBatchesTableReferences
    extends BaseReferences<_$AppDatabase, $SyncBatchesTable, SyncBatche> {
  $$SyncBatchesTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static MultiTypedResultKey<$ReadingsTable, List<Reading>> _readingsRefsTable(
          _$AppDatabase db) =>
      MultiTypedResultKey.fromTable(db.readings,
          aliasName:
              $_aliasNameGenerator(db.syncBatches.id, db.readings.syncBatchId));

  $$ReadingsTableProcessedTableManager get readingsRefs {
    final manager = $$ReadingsTableTableManager($_db, $_db.readings)
        .filter((f) => f.syncBatchId.id.sqlEquals($_itemColumn<String>('id')!));

    final cache = $_typedResult.readTableOrNull(_readingsRefsTable($_db));
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: cache));
  }
}

class $$SyncBatchesTableFilterComposer
    extends Composer<_$AppDatabase, $SyncBatchesTable> {
  $$SyncBatchesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get status => $composableBuilder(
      column: $table.status, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get archivePath => $composableBuilder(
      column: $table.archivePath, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get readingCount => $composableBuilder(
      column: $table.readingCount, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get retryCount => $composableBuilder(
      column: $table.retryCount, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get lastError => $composableBuilder(
      column: $table.lastError, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
      column: $table.createdAt, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get lastAttemptAt => $composableBuilder(
      column: $table.lastAttemptAt, builder: (column) => ColumnFilters(column));

  Expression<bool> readingsRefs(
      Expression<bool> Function($$ReadingsTableFilterComposer f) f) {
    final $$ReadingsTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.id,
        referencedTable: $db.readings,
        getReferencedColumn: (t) => t.syncBatchId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$ReadingsTableFilterComposer(
              $db: $db,
              $table: $db.readings,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$SyncBatchesTableOrderingComposer
    extends Composer<_$AppDatabase, $SyncBatchesTable> {
  $$SyncBatchesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get status => $composableBuilder(
      column: $table.status, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get archivePath => $composableBuilder(
      column: $table.archivePath, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get readingCount => $composableBuilder(
      column: $table.readingCount,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get retryCount => $composableBuilder(
      column: $table.retryCount, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get lastError => $composableBuilder(
      column: $table.lastError, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
      column: $table.createdAt, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get lastAttemptAt => $composableBuilder(
      column: $table.lastAttemptAt,
      builder: (column) => ColumnOrderings(column));
}

class $$SyncBatchesTableAnnotationComposer
    extends Composer<_$AppDatabase, $SyncBatchesTable> {
  $$SyncBatchesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<String> get archivePath => $composableBuilder(
      column: $table.archivePath, builder: (column) => column);

  GeneratedColumn<int> get readingCount => $composableBuilder(
      column: $table.readingCount, builder: (column) => column);

  GeneratedColumn<int> get retryCount => $composableBuilder(
      column: $table.retryCount, builder: (column) => column);

  GeneratedColumn<String> get lastError =>
      $composableBuilder(column: $table.lastError, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<DateTime> get lastAttemptAt => $composableBuilder(
      column: $table.lastAttemptAt, builder: (column) => column);

  Expression<T> readingsRefs<T extends Object>(
      Expression<T> Function($$ReadingsTableAnnotationComposer a) f) {
    final $$ReadingsTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.id,
        referencedTable: $db.readings,
        getReferencedColumn: (t) => t.syncBatchId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$ReadingsTableAnnotationComposer(
              $db: $db,
              $table: $db.readings,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$SyncBatchesTableTableManager extends RootTableManager<
    _$AppDatabase,
    $SyncBatchesTable,
    SyncBatche,
    $$SyncBatchesTableFilterComposer,
    $$SyncBatchesTableOrderingComposer,
    $$SyncBatchesTableAnnotationComposer,
    $$SyncBatchesTableCreateCompanionBuilder,
    $$SyncBatchesTableUpdateCompanionBuilder,
    (SyncBatche, $$SyncBatchesTableReferences),
    SyncBatche,
    PrefetchHooks Function({bool readingsRefs})> {
  $$SyncBatchesTableTableManager(_$AppDatabase db, $SyncBatchesTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SyncBatchesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SyncBatchesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SyncBatchesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> id = const Value.absent(),
            Value<String> status = const Value.absent(),
            Value<String?> archivePath = const Value.absent(),
            Value<int> readingCount = const Value.absent(),
            Value<int> retryCount = const Value.absent(),
            Value<String?> lastError = const Value.absent(),
            Value<DateTime> createdAt = const Value.absent(),
            Value<DateTime?> lastAttemptAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              SyncBatchesCompanion(
            id: id,
            status: status,
            archivePath: archivePath,
            readingCount: readingCount,
            retryCount: retryCount,
            lastError: lastError,
            createdAt: createdAt,
            lastAttemptAt: lastAttemptAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String id,
            Value<String> status = const Value.absent(),
            Value<String?> archivePath = const Value.absent(),
            required int readingCount,
            Value<int> retryCount = const Value.absent(),
            Value<String?> lastError = const Value.absent(),
            required DateTime createdAt,
            Value<DateTime?> lastAttemptAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              SyncBatchesCompanion.insert(
            id: id,
            status: status,
            archivePath: archivePath,
            readingCount: readingCount,
            retryCount: retryCount,
            lastError: lastError,
            createdAt: createdAt,
            lastAttemptAt: lastAttemptAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (
                    e.readTable(table),
                    $$SyncBatchesTableReferences(db, table, e)
                  ))
              .toList(),
          prefetchHooksCallback: ({readingsRefs = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [if (readingsRefs) db.readings],
              addJoins: null,
              getPrefetchedDataCallback: (items) async {
                return [
                  if (readingsRefs)
                    await $_getPrefetchedData<SyncBatche, $SyncBatchesTable,
                            Reading>(
                        currentTable: table,
                        referencedTable:
                            $$SyncBatchesTableReferences._readingsRefsTable(db),
                        managerFromTypedResult: (p0) =>
                            $$SyncBatchesTableReferences(db, table, p0)
                                .readingsRefs,
                        referencedItemsForCurrentItem:
                            (item, referencedItems) => referencedItems
                                .where((e) => e.syncBatchId == item.id),
                        typedResults: items)
                ];
              },
            );
          },
        ));
}

typedef $$SyncBatchesTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $SyncBatchesTable,
    SyncBatche,
    $$SyncBatchesTableFilterComposer,
    $$SyncBatchesTableOrderingComposer,
    $$SyncBatchesTableAnnotationComposer,
    $$SyncBatchesTableCreateCompanionBuilder,
    $$SyncBatchesTableUpdateCompanionBuilder,
    (SyncBatche, $$SyncBatchesTableReferences),
    SyncBatche,
    PrefetchHooks Function({bool readingsRefs})>;
typedef $$ReadingsTableCreateCompanionBuilder = ReadingsCompanion Function({
  required String id,
  Value<int?> remoteId,
  required int meterRemoteId,
  required double readingValue,
  required DateTime readingDate,
  Value<int?> capturedPeriodId,
  Value<String> readingCategory,
  Value<bool> isEstimated,
  Value<String?> remarks,
  Value<String?> imageLocalPath,
  Value<String?> imageSecondaryLocalPath,
  Value<int?> imageAttachmentRemoteId,
  Value<String> syncStatus,
  Value<int> syncAttempts,
  Value<String?> syncBatchId,
  Value<String?> lastError,
  required DateTime createdAt,
  required DateTime updatedAt,
  Value<int> rowid,
});
typedef $$ReadingsTableUpdateCompanionBuilder = ReadingsCompanion Function({
  Value<String> id,
  Value<int?> remoteId,
  Value<int> meterRemoteId,
  Value<double> readingValue,
  Value<DateTime> readingDate,
  Value<int?> capturedPeriodId,
  Value<String> readingCategory,
  Value<bool> isEstimated,
  Value<String?> remarks,
  Value<String?> imageLocalPath,
  Value<String?> imageSecondaryLocalPath,
  Value<int?> imageAttachmentRemoteId,
  Value<String> syncStatus,
  Value<int> syncAttempts,
  Value<String?> syncBatchId,
  Value<String?> lastError,
  Value<DateTime> createdAt,
  Value<DateTime> updatedAt,
  Value<int> rowid,
});

final class $$ReadingsTableReferences
    extends BaseReferences<_$AppDatabase, $ReadingsTable, Reading> {
  $$ReadingsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $MetersTable _meterRemoteIdTable(_$AppDatabase db) =>
      db.meters.createAlias(
          $_aliasNameGenerator(db.readings.meterRemoteId, db.meters.remoteId));

  $$MetersTableProcessedTableManager get meterRemoteId {
    final $_column = $_itemColumn<int>('meter_remote_id')!;

    final manager = $$MetersTableTableManager($_db, $_db.meters)
        .filter((f) => f.remoteId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_meterRemoteIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: [item]));
  }

  static $SyncBatchesTable _syncBatchIdTable(_$AppDatabase db) =>
      db.syncBatches.createAlias(
          $_aliasNameGenerator(db.readings.syncBatchId, db.syncBatches.id));

  $$SyncBatchesTableProcessedTableManager? get syncBatchId {
    final $_column = $_itemColumn<String>('sync_batch_id');
    if ($_column == null) return null;
    final manager = $$SyncBatchesTableTableManager($_db, $_db.syncBatches)
        .filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_syncBatchIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: [item]));
  }
}

class $$ReadingsTableFilterComposer
    extends Composer<_$AppDatabase, $ReadingsTable> {
  $$ReadingsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get remoteId => $composableBuilder(
      column: $table.remoteId, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get readingValue => $composableBuilder(
      column: $table.readingValue, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get readingDate => $composableBuilder(
      column: $table.readingDate, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get capturedPeriodId => $composableBuilder(
      column: $table.capturedPeriodId,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get readingCategory => $composableBuilder(
      column: $table.readingCategory,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<bool> get isEstimated => $composableBuilder(
      column: $table.isEstimated, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get remarks => $composableBuilder(
      column: $table.remarks, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get imageLocalPath => $composableBuilder(
      column: $table.imageLocalPath,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get imageSecondaryLocalPath => $composableBuilder(
      column: $table.imageSecondaryLocalPath,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get imageAttachmentRemoteId => $composableBuilder(
      column: $table.imageAttachmentRemoteId,
      builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get syncStatus => $composableBuilder(
      column: $table.syncStatus, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get syncAttempts => $composableBuilder(
      column: $table.syncAttempts, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get lastError => $composableBuilder(
      column: $table.lastError, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
      column: $table.createdAt, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get updatedAt => $composableBuilder(
      column: $table.updatedAt, builder: (column) => ColumnFilters(column));

  $$MetersTableFilterComposer get meterRemoteId {
    final $$MetersTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.meterRemoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableFilterComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }

  $$SyncBatchesTableFilterComposer get syncBatchId {
    final $$SyncBatchesTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.syncBatchId,
        referencedTable: $db.syncBatches,
        getReferencedColumn: (t) => t.id,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$SyncBatchesTableFilterComposer(
              $db: $db,
              $table: $db.syncBatches,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$ReadingsTableOrderingComposer
    extends Composer<_$AppDatabase, $ReadingsTable> {
  $$ReadingsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get remoteId => $composableBuilder(
      column: $table.remoteId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get readingValue => $composableBuilder(
      column: $table.readingValue,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get readingDate => $composableBuilder(
      column: $table.readingDate, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get capturedPeriodId => $composableBuilder(
      column: $table.capturedPeriodId,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get readingCategory => $composableBuilder(
      column: $table.readingCategory,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<bool> get isEstimated => $composableBuilder(
      column: $table.isEstimated, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get remarks => $composableBuilder(
      column: $table.remarks, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get imageLocalPath => $composableBuilder(
      column: $table.imageLocalPath,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get imageSecondaryLocalPath => $composableBuilder(
      column: $table.imageSecondaryLocalPath,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get imageAttachmentRemoteId => $composableBuilder(
      column: $table.imageAttachmentRemoteId,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get syncStatus => $composableBuilder(
      column: $table.syncStatus, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get syncAttempts => $composableBuilder(
      column: $table.syncAttempts,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get lastError => $composableBuilder(
      column: $table.lastError, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
      column: $table.createdAt, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get updatedAt => $composableBuilder(
      column: $table.updatedAt, builder: (column) => ColumnOrderings(column));

  $$MetersTableOrderingComposer get meterRemoteId {
    final $$MetersTableOrderingComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.meterRemoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableOrderingComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }

  $$SyncBatchesTableOrderingComposer get syncBatchId {
    final $$SyncBatchesTableOrderingComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.syncBatchId,
        referencedTable: $db.syncBatches,
        getReferencedColumn: (t) => t.id,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$SyncBatchesTableOrderingComposer(
              $db: $db,
              $table: $db.syncBatches,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$ReadingsTableAnnotationComposer
    extends Composer<_$AppDatabase, $ReadingsTable> {
  $$ReadingsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<int> get remoteId =>
      $composableBuilder(column: $table.remoteId, builder: (column) => column);

  GeneratedColumn<double> get readingValue => $composableBuilder(
      column: $table.readingValue, builder: (column) => column);

  GeneratedColumn<DateTime> get readingDate => $composableBuilder(
      column: $table.readingDate, builder: (column) => column);

  GeneratedColumn<int> get capturedPeriodId => $composableBuilder(
      column: $table.capturedPeriodId, builder: (column) => column);

  GeneratedColumn<String> get readingCategory => $composableBuilder(
      column: $table.readingCategory, builder: (column) => column);

  GeneratedColumn<bool> get isEstimated => $composableBuilder(
      column: $table.isEstimated, builder: (column) => column);

  GeneratedColumn<String> get remarks =>
      $composableBuilder(column: $table.remarks, builder: (column) => column);

  GeneratedColumn<String> get imageLocalPath => $composableBuilder(
      column: $table.imageLocalPath, builder: (column) => column);

  GeneratedColumn<String> get imageSecondaryLocalPath => $composableBuilder(
      column: $table.imageSecondaryLocalPath, builder: (column) => column);

  GeneratedColumn<int> get imageAttachmentRemoteId => $composableBuilder(
      column: $table.imageAttachmentRemoteId, builder: (column) => column);

  GeneratedColumn<String> get syncStatus => $composableBuilder(
      column: $table.syncStatus, builder: (column) => column);

  GeneratedColumn<int> get syncAttempts => $composableBuilder(
      column: $table.syncAttempts, builder: (column) => column);

  GeneratedColumn<String> get lastError =>
      $composableBuilder(column: $table.lastError, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<DateTime> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);

  $$MetersTableAnnotationComposer get meterRemoteId {
    final $$MetersTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.meterRemoteId,
        referencedTable: $db.meters,
        getReferencedColumn: (t) => t.remoteId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$MetersTableAnnotationComposer(
              $db: $db,
              $table: $db.meters,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }

  $$SyncBatchesTableAnnotationComposer get syncBatchId {
    final $$SyncBatchesTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.syncBatchId,
        referencedTable: $db.syncBatches,
        getReferencedColumn: (t) => t.id,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$SyncBatchesTableAnnotationComposer(
              $db: $db,
              $table: $db.syncBatches,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$ReadingsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $ReadingsTable,
    Reading,
    $$ReadingsTableFilterComposer,
    $$ReadingsTableOrderingComposer,
    $$ReadingsTableAnnotationComposer,
    $$ReadingsTableCreateCompanionBuilder,
    $$ReadingsTableUpdateCompanionBuilder,
    (Reading, $$ReadingsTableReferences),
    Reading,
    PrefetchHooks Function({bool meterRemoteId, bool syncBatchId})> {
  $$ReadingsTableTableManager(_$AppDatabase db, $ReadingsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ReadingsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ReadingsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ReadingsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> id = const Value.absent(),
            Value<int?> remoteId = const Value.absent(),
            Value<int> meterRemoteId = const Value.absent(),
            Value<double> readingValue = const Value.absent(),
            Value<DateTime> readingDate = const Value.absent(),
            Value<int?> capturedPeriodId = const Value.absent(),
            Value<String> readingCategory = const Value.absent(),
            Value<bool> isEstimated = const Value.absent(),
            Value<String?> remarks = const Value.absent(),
            Value<String?> imageLocalPath = const Value.absent(),
            Value<String?> imageSecondaryLocalPath = const Value.absent(),
            Value<int?> imageAttachmentRemoteId = const Value.absent(),
            Value<String> syncStatus = const Value.absent(),
            Value<int> syncAttempts = const Value.absent(),
            Value<String?> syncBatchId = const Value.absent(),
            Value<String?> lastError = const Value.absent(),
            Value<DateTime> createdAt = const Value.absent(),
            Value<DateTime> updatedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              ReadingsCompanion(
            id: id,
            remoteId: remoteId,
            meterRemoteId: meterRemoteId,
            readingValue: readingValue,
            readingDate: readingDate,
            capturedPeriodId: capturedPeriodId,
            readingCategory: readingCategory,
            isEstimated: isEstimated,
            remarks: remarks,
            imageLocalPath: imageLocalPath,
            imageSecondaryLocalPath: imageSecondaryLocalPath,
            imageAttachmentRemoteId: imageAttachmentRemoteId,
            syncStatus: syncStatus,
            syncAttempts: syncAttempts,
            syncBatchId: syncBatchId,
            lastError: lastError,
            createdAt: createdAt,
            updatedAt: updatedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String id,
            Value<int?> remoteId = const Value.absent(),
            required int meterRemoteId,
            required double readingValue,
            required DateTime readingDate,
            Value<int?> capturedPeriodId = const Value.absent(),
            Value<String> readingCategory = const Value.absent(),
            Value<bool> isEstimated = const Value.absent(),
            Value<String?> remarks = const Value.absent(),
            Value<String?> imageLocalPath = const Value.absent(),
            Value<String?> imageSecondaryLocalPath = const Value.absent(),
            Value<int?> imageAttachmentRemoteId = const Value.absent(),
            Value<String> syncStatus = const Value.absent(),
            Value<int> syncAttempts = const Value.absent(),
            Value<String?> syncBatchId = const Value.absent(),
            Value<String?> lastError = const Value.absent(),
            required DateTime createdAt,
            required DateTime updatedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              ReadingsCompanion.insert(
            id: id,
            remoteId: remoteId,
            meterRemoteId: meterRemoteId,
            readingValue: readingValue,
            readingDate: readingDate,
            capturedPeriodId: capturedPeriodId,
            readingCategory: readingCategory,
            isEstimated: isEstimated,
            remarks: remarks,
            imageLocalPath: imageLocalPath,
            imageSecondaryLocalPath: imageSecondaryLocalPath,
            imageAttachmentRemoteId: imageAttachmentRemoteId,
            syncStatus: syncStatus,
            syncAttempts: syncAttempts,
            syncBatchId: syncBatchId,
            lastError: lastError,
            createdAt: createdAt,
            updatedAt: updatedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) =>
                  (e.readTable(table), $$ReadingsTableReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: (
              {meterRemoteId = false, syncBatchId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins: <
                  T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic>>(state) {
                if (meterRemoteId) {
                  state = state.withJoin(
                    currentTable: table,
                    currentColumn: table.meterRemoteId,
                    referencedTable:
                        $$ReadingsTableReferences._meterRemoteIdTable(db),
                    referencedColumn: $$ReadingsTableReferences
                        ._meterRemoteIdTable(db)
                        .remoteId,
                  ) as T;
                }
                if (syncBatchId) {
                  state = state.withJoin(
                    currentTable: table,
                    currentColumn: table.syncBatchId,
                    referencedTable:
                        $$ReadingsTableReferences._syncBatchIdTable(db),
                    referencedColumn:
                        $$ReadingsTableReferences._syncBatchIdTable(db).id,
                  ) as T;
                }

                return state;
              },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ));
}

typedef $$ReadingsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $ReadingsTable,
    Reading,
    $$ReadingsTableFilterComposer,
    $$ReadingsTableOrderingComposer,
    $$ReadingsTableAnnotationComposer,
    $$ReadingsTableCreateCompanionBuilder,
    $$ReadingsTableUpdateCompanionBuilder,
    (Reading, $$ReadingsTableReferences),
    Reading,
    PrefetchHooks Function({bool meterRemoteId, bool syncBatchId})>;
typedef $$MeterReadingHistoriesTableCreateCompanionBuilder
    = MeterReadingHistoriesCompanion Function({
  required String entryKey,
  required int meterRemoteId,
  required double readingValue,
  required DateTime readingDate,
  required String source,
  required DateTime syncedAt,
  Value<int> rowid,
});
typedef $$MeterReadingHistoriesTableUpdateCompanionBuilder
    = MeterReadingHistoriesCompanion Function({
  Value<String> entryKey,
  Value<int> meterRemoteId,
  Value<double> readingValue,
  Value<DateTime> readingDate,
  Value<String> source,
  Value<DateTime> syncedAt,
  Value<int> rowid,
});

class $$MeterReadingHistoriesTableFilterComposer
    extends Composer<_$AppDatabase, $MeterReadingHistoriesTable> {
  $$MeterReadingHistoriesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get entryKey => $composableBuilder(
      column: $table.entryKey, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get meterRemoteId => $composableBuilder(
      column: $table.meterRemoteId, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get readingValue => $composableBuilder(
      column: $table.readingValue, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get readingDate => $composableBuilder(
      column: $table.readingDate, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get source => $composableBuilder(
      column: $table.source, builder: (column) => ColumnFilters(column));

  ColumnFilters<DateTime> get syncedAt => $composableBuilder(
      column: $table.syncedAt, builder: (column) => ColumnFilters(column));
}

class $$MeterReadingHistoriesTableOrderingComposer
    extends Composer<_$AppDatabase, $MeterReadingHistoriesTable> {
  $$MeterReadingHistoriesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get entryKey => $composableBuilder(
      column: $table.entryKey, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get meterRemoteId => $composableBuilder(
      column: $table.meterRemoteId,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get readingValue => $composableBuilder(
      column: $table.readingValue,
      builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get readingDate => $composableBuilder(
      column: $table.readingDate, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get source => $composableBuilder(
      column: $table.source, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<DateTime> get syncedAt => $composableBuilder(
      column: $table.syncedAt, builder: (column) => ColumnOrderings(column));
}

class $$MeterReadingHistoriesTableAnnotationComposer
    extends Composer<_$AppDatabase, $MeterReadingHistoriesTable> {
  $$MeterReadingHistoriesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get entryKey =>
      $composableBuilder(column: $table.entryKey, builder: (column) => column);

  GeneratedColumn<int> get meterRemoteId => $composableBuilder(
      column: $table.meterRemoteId, builder: (column) => column);

  GeneratedColumn<double> get readingValue => $composableBuilder(
      column: $table.readingValue, builder: (column) => column);

  GeneratedColumn<DateTime> get readingDate => $composableBuilder(
      column: $table.readingDate, builder: (column) => column);

  GeneratedColumn<String> get source =>
      $composableBuilder(column: $table.source, builder: (column) => column);

  GeneratedColumn<DateTime> get syncedAt =>
      $composableBuilder(column: $table.syncedAt, builder: (column) => column);
}

class $$MeterReadingHistoriesTableTableManager extends RootTableManager<
    _$AppDatabase,
    $MeterReadingHistoriesTable,
    MeterReadingHistory,
    $$MeterReadingHistoriesTableFilterComposer,
    $$MeterReadingHistoriesTableOrderingComposer,
    $$MeterReadingHistoriesTableAnnotationComposer,
    $$MeterReadingHistoriesTableCreateCompanionBuilder,
    $$MeterReadingHistoriesTableUpdateCompanionBuilder,
    (
      MeterReadingHistory,
      BaseReferences<_$AppDatabase, $MeterReadingHistoriesTable,
          MeterReadingHistory>
    ),
    MeterReadingHistory,
    PrefetchHooks Function()> {
  $$MeterReadingHistoriesTableTableManager(
      _$AppDatabase db, $MeterReadingHistoriesTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MeterReadingHistoriesTableFilterComposer(
                  $db: db, $table: table),
          createOrderingComposer: () =>
              $$MeterReadingHistoriesTableOrderingComposer(
                  $db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MeterReadingHistoriesTableAnnotationComposer(
                  $db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> entryKey = const Value.absent(),
            Value<int> meterRemoteId = const Value.absent(),
            Value<double> readingValue = const Value.absent(),
            Value<DateTime> readingDate = const Value.absent(),
            Value<String> source = const Value.absent(),
            Value<DateTime> syncedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              MeterReadingHistoriesCompanion(
            entryKey: entryKey,
            meterRemoteId: meterRemoteId,
            readingValue: readingValue,
            readingDate: readingDate,
            source: source,
            syncedAt: syncedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String entryKey,
            required int meterRemoteId,
            required double readingValue,
            required DateTime readingDate,
            required String source,
            required DateTime syncedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              MeterReadingHistoriesCompanion.insert(
            entryKey: entryKey,
            meterRemoteId: meterRemoteId,
            readingValue: readingValue,
            readingDate: readingDate,
            source: source,
            syncedAt: syncedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$MeterReadingHistoriesTableProcessedTableManager
    = ProcessedTableManager<
        _$AppDatabase,
        $MeterReadingHistoriesTable,
        MeterReadingHistory,
        $$MeterReadingHistoriesTableFilterComposer,
        $$MeterReadingHistoriesTableOrderingComposer,
        $$MeterReadingHistoriesTableAnnotationComposer,
        $$MeterReadingHistoriesTableCreateCompanionBuilder,
        $$MeterReadingHistoriesTableUpdateCompanionBuilder,
        (
          MeterReadingHistory,
          BaseReferences<_$AppDatabase, $MeterReadingHistoriesTable,
              MeterReadingHistory>
        ),
        MeterReadingHistory,
        PrefetchHooks Function()>;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$CustomersTableTableManager get customers =>
      $$CustomersTableTableManager(_db, _db.customers);
  $$MetersTableTableManager get meters =>
      $$MetersTableTableManager(_db, _db.meters);
  $$AssignmentsTableTableManager get assignments =>
      $$AssignmentsTableTableManager(_db, _db.assignments);
  $$PeriodsTableTableManager get periods =>
      $$PeriodsTableTableManager(_db, _db.periods);
  $$SyncBatchesTableTableManager get syncBatches =>
      $$SyncBatchesTableTableManager(_db, _db.syncBatches);
  $$ReadingsTableTableManager get readings =>
      $$ReadingsTableTableManager(_db, _db.readings);
  $$MeterReadingHistoriesTableTableManager get meterReadingHistories =>
      $$MeterReadingHistoriesTableTableManager(_db, _db.meterReadingHistories);
}
