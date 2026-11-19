package org.enade.identity.application;

import org.enade.identity.domain.exception.SessionExpiredException;
import org.enade.identity.domain.model.AuthSession;
import org.enade.identity.domain.model.UserAccount;
import org.enade.identity.infrastructure.redis.SessionRepository;
import org.enade.identity.presentation.dto.AuthSessionResponseDto;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;

@ApplicationScoped
public class SessionUseCase {

    private static final int TOKEN_BYTES = 32;
    private static final long SESSION_DURATION_SECONDS = 1800;

    private final SecureRandom secureRandom = new SecureRandom();

    @Inject
    SessionRepository sessionRepository;

    public AuthSessionResponseDto createSession(UserAccount user) {
        if (user == null
                || user.getUsername() == null
                || user.getUsername().isBlank()
                || user.getRole() == null) {
            throw new IllegalArgumentException(
                    "Os dados do usuário são obrigatórios para criar uma sessão."
            );
        }

        Instant createdAt = Instant.now();
        Instant expiresAt = createdAt.plusSeconds(SESSION_DURATION_SECONDS);
        String token = generateToken();

        AuthSession session = new AuthSession(
                token,
                user.getUsername(),
                user.getRole(),
                createdAt,
                expiresAt,
                false
        );

        sessionRepository.save(session);

        return toResponse(session);
    }

    public AuthSessionResponseDto getCurrentSession(String sessionToken) {
        AuthSession session = findValidSession(sessionToken);
        return toResponse(session);
    }

    public AuthSessionResponseDto renewSession(String sessionToken) {
        AuthSession currentSession = findValidSession(sessionToken);

        Instant createdAt = Instant.now();
        Instant expiresAt = createdAt.plusSeconds(SESSION_DURATION_SECONDS);
        String renewedToken = generateToken();

        AuthSession renewedSession = new AuthSession(
                renewedToken,
                currentSession.getUsername(),
                currentSession.getRole(),
                createdAt,
                expiresAt,
                false
        );

        sessionRepository.deleteByToken(sessionToken);
        sessionRepository.save(renewedSession);

        return toResponse(renewedSession);
    }

    public void logout(String sessionToken) {
        if (sessionToken == null || sessionToken.isBlank()) {
            throw new IllegalArgumentException("O token da sessão é obrigatório.");
        }

        AuthSession session = sessionRepository.findByToken(sessionToken)
                .orElseThrow(() -> new IllegalArgumentException(
                        "A sessão não existe ou já foi revogada."
                ));

        if (session.isRevoked()) {
            throw new IllegalArgumentException(
                    "A sessão não existe ou já foi revogada."
            );
        }

        sessionRepository.deleteByToken(sessionToken);
    }

    private AuthSession findValidSession(String sessionToken) {
        if (sessionToken == null || sessionToken.isBlank()) {
            throw new IllegalArgumentException("O token da sessão é obrigatório.");
        }

        AuthSession session = sessionRepository.findByToken(sessionToken)
                .orElseThrow(SessionExpiredException::new);

        if (session.isRevoked()
                || session.getExpiresAt() == null
                || !session.getExpiresAt().isAfter(Instant.now())) {
            sessionRepository.deleteByToken(sessionToken);
            throw new SessionExpiredException();
        }

        return session;
    }

    private String generateToken() {
        byte[] tokenBytes = new byte[TOKEN_BYTES];
        secureRandom.nextBytes(tokenBytes);

        return Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(tokenBytes);
    }

    private AuthSessionResponseDto toResponse(AuthSession session) {
        return new AuthSessionResponseDto(
                session.getToken(),
                session.getUsername(),
                session.getRole().name(),
                session.getExpiresAt()
        );
    }
}
