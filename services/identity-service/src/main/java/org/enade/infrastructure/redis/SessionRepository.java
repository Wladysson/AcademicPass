package org.enade.identity.infrastructure.redis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.enade.identity.domain.model.AuthSession;
import org.enade.identity.domain.model.UserRole;

import io.quarkus.redis.datasource.RedisDataSource;
import io.quarkus.redis.datasource.value.ValueCommands;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Optional;

@ApplicationScoped
public class SessionRepository {

    private static final String SESSION_KEY_PREFIX = "enade:identity:session:";
    private static final String SESSION_TTL_PREFIX = "enade:identity:session-ttl:";
    private static final String SESSION_KEY_SEPARATOR = ":";

    @Inject
    RedisDataSource redisDataSource;

    @Inject
    ObjectMapper objectMapper;

    public void save(AuthSession session) {
        if (session == null) {
            throw new IllegalArgumentException("A sessão é obrigatória.");
        }

        if (!session.isValid()) {
            throw new IllegalArgumentException(
                    "Não é possível persistir uma sessão inválida ou expirada."
            );
        }

        long ttlSeconds = Duration.between(
                Instant.now(),
                session.getExpiresAt()
        ).getSeconds();

        if (ttlSeconds <= 0) {
            throw new IllegalArgumentException(
                    "A sessão precisa ter uma expiração futura."
            );
        }

        String key = sessionKey(session.getToken());
        String value = serialize(session);

        ValueCommands<String, String> commands =
                redisDataSource.value(String.class);

        commands.setex(key, ttlSeconds, value);
    }

    public Optional<AuthSession> findByToken(String token) {
        validateToken(token);

        ValueCommands<String, String> commands =
                redisDataSource.value(String.class);

        String value = commands.get(sessionKey(token));

        if (value == null || value.isBlank()) {
            return Optional.empty();
        }

        AuthSession session = deserialize(value, token);

        if (!session.isValid()) {
            deleteByToken(token);
            return Optional.empty();
        }

        return Optional.of(session);
    }

    public void deleteByToken(String token) {
        validateToken(token);

        redisDataSource.key(String.class)
                .del(sessionKey(token));
    }

    public void checkAvailability() {
        redisDataSource.execute("PING");
    }

    private String serialize(AuthSession session) {
        try {
            ObjectNode node = objectMapper.createObjectNode();

            node.put("username", session.getUsername());
            node.put("role", session.getRole().name());
            node.put("createdAt", session.getCreatedAt().toString());
            node.put("expiresAt", session.getExpiresAt().toString());
            node.put("revoked", session.isRevoked());

            return objectMapper.writeValueAsString(node);
        } catch (Exception exception) {
            throw new IllegalStateException(
                    "Não foi possível serializar a sessão.",
                    exception
            );
        }
    }

    private AuthSession deserialize(String value, String token) {
        try {
            JsonNode node = objectMapper.readTree(value);

            String username = requiredText(node, "username");
            String roleValue = requiredText(node, "role");
            String createdAtValue = requiredText(node, "createdAt");
            String expiresAtValue = requiredText(node, "expiresAt");

            JsonNode revokedNode = node.get("revoked");

            if (revokedNode == null || !revokedNode.isBoolean()) {
                throw new IllegalStateException(
                        "O estado de revogação da sessão é inválido."
                );
            }

            UserRole role = UserRole.valueOf(roleValue);

            return new AuthSession(
                    token,
                    username,
                    role,
                    Instant.parse(createdAtValue),
                    Instant.parse(expiresAtValue),
                    revokedNode.booleanValue()
            );
        } catch (Exception exception) {
            if (exception instanceof IllegalStateException illegalStateException
                    && illegalStateException.getMessage() != null
                    && illegalStateException.getMessage().startsWith(
                    "Os dados da sessão")) {
                throw illegalStateException;
            }

            throw new IllegalStateException(
                    "Não foi possível recuperar a sessão armazenada no Redis.",
                    exception
            );
        }
    }

    private String requiredText(JsonNode node, String field) {
        JsonNode value = node.get(field);

        if (value == null || !value.isTextual() || value.asText().isBlank()) {
            throw new IllegalStateException(
                    "Os dados da sessão estão incompletos: " + field + "."
            );
        }

        return value.asText();
    }

    private String sessionKey(String token) {
        return SESSION_KEY_PREFIX + hashToken(token);
    }

    private String hashToken(String token) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(token.getBytes(StandardCharsets.UTF_8));

            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(
                    "O algoritmo SHA-256 não está disponível.",
                    exception
            );
        }
    }

    private void validateToken(String token) {
        if (token == null || token.isBlank()) {
            throw new IllegalArgumentException(
                    "O token da sessão é obrigatório."
            );
        }
    }
}
