/// Typed API error carrying the backend's stable `code`.
class ApiException implements Exception {
  ApiException(this.code, this.message, {this.status, this.details});

  final String code;
  final String message;
  final int? status;
  final Map<String, dynamic>? details;

  bool get isAuth => status == 401;

  @override
  String toString() => 'ApiException($code, $message)';
}
