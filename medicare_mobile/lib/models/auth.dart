class LoginRequest {
  final String username;
  final String password;
  final String? empresa;

  LoginRequest({
    required this.username,
    required this.password,
    this.empresa,
  });

  Map<String, dynamic> toJson() => {
    'username': username,
    'password': password,
    'empresa': empresa,
  };
}

class LoginResponse {
  final String accessToken;
  final String tokenType;
  final int expiresIn;
  final Map<String, dynamic> user;

  LoginResponse({
    required this.accessToken,
    required this.tokenType,
    required this.expiresIn,
    required this.user,
  });

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      accessToken: json['access_token'] as String,
      tokenType: json['token_type'] as String,
      expiresIn: json['expires_in'] as int,
      user: json['user'] as Map<String, dynamic>,
    );
  }

  String get username => user['username'] as String? ?? '';
  String get rol => user['rol'] as String? ?? '';
  String get empresa => user['empresa'] as String? ?? '';
}

class UserSession {
  final String accessToken;
  final String username;
  final String rol;
  final String empresa;
  final DateTime expiresAt;

  UserSession({
    required this.accessToken,
    required this.username,
    required this.rol,
    required this.empresa,
    required this.expiresAt,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);

  Map<String, dynamic> toJson() => {
    'access_token': accessToken,
    'username': username,
    'rol': rol,
    'empresa': empresa,
    'expires_at': expiresAt.toIso8601String(),
  };

  factory UserSession.fromJson(Map<String, dynamic> json) {
    return UserSession(
      accessToken: json['access_token'] as String,
      username: json['username'] as String,
      rol: json['rol'] as String,
      empresa: json['empresa'] as String,
      expiresAt: DateTime.parse(json['expires_at'] as String),
    );
  }
}
