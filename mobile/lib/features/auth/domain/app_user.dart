class AppUser {
  const AppUser({required this.id, required this.username, required this.displayName, required this.role});

  final int id;
  final String username;
  final String displayName;
  final String role;

  bool get isCoordinator => role == 'coordinator';
  bool get isTimer => role == 'timer';

  factory AppUser.fromJson(Map<String, dynamic> j) => AppUser(
        id: j['id'] as int,
        username: j['username'] as String,
        displayName: j['display_name'] as String,
        role: j['role'] as String,
      );
}
