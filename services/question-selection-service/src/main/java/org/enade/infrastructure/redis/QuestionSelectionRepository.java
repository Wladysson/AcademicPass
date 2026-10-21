package org.enade.selection.infrastructure.redis;

import java.time.Duration;
import java.util.List;
import java.util.Optional;

import org.enade.selection.domain.model.QuestionSelection;
import org.enade.selection.domain.model.SelectedQuestion;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import io.quarkus.redis.datasource.RedisDataSource;
import io.quarkus.redis.datasource.keys.KeyCommands;
import io.quarkus.redis.datasource.value.SetArgs;
import io.quarkus.redis.datasource.value.ValueCommands;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class QuestionSelectionRepository {

    private static final String KEY_PREFIX = "enade:selection:user:";

    private final ValueCommands<String, String> valueCommands;
    private final KeyCommands<String> keyCommands;
    private final ObjectMapper objectMapper;
    private final Duration ttl;

    @Inject
    public QuestionSelectionRepository(
            RedisDataSource redisDataSource,
            ObjectMapper objectMapper
    ) {
        this.valueCommands = redisDataSource.value(String.class, String.class);
        this.keyCommands = redisDataSource.key();
        this.objectMapper = objectMapper;
        this.ttl = Duration.ofSeconds(
                Long.parseLong(
                        System.getProperty(
                                "selection.ttl.seconds",
                                "86400"
                        )
                )
        );

        if (ttl.isZero() || ttl.isNegative()) {
            throw new IllegalArgumentException(
                    "O TTL da seleção deve ser maior que zero."
            );
        }
    }

    public Optional<QuestionSelection> findByUserId(String userId) {
        String key = buildKey(userId);
        String json = valueCommands.get(key);

        if (json == null) {
            return Optional.empty();
        }

        try {
            SelectionDocument document = objectMapper.readValue(
                    json,
                    SelectionDocument.class
            );

            return Optional.of(
                    new QuestionSelection(
                            document.userId(),
                            document.questions()
                    )
            );
        } catch (JsonProcessingException | IllegalArgumentException exception) {
            throw new IllegalStateException(
                    "Não foi possível recuperar a seleção armazenada no Redis.",
                    exception
            );
        }
    }

    public void save(QuestionSelection selection) {
        if (selection == null) {
            throw new IllegalArgumentException(
                    "A seleção não pode ser nula."
            );
        }

        String key = buildKey(selection.userId());

        SelectionDocument document = new SelectionDocument(
                selection.userId(),
                selection.questions()
        );

        try {
            String json = objectMapper.writeValueAsString(document);

            valueCommands.set(
                    key,
                    json,
                    new SetArgs().ex(ttl.toSeconds())
            );
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException(
                    "Não foi possível serializar a seleção para o Redis.",
                    exception
            );
        }
    }

    public void deleteByUserId(String userId) {
        keyCommands.del(buildKey(userId));
    }

    private String buildKey(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador do usuário é obrigatório."
            );
        }

        return KEY_PREFIX + userId.trim();
    }

    public record SelectionDocument(
            String userId,
            List<SelectedQuestion> questions
    ) {
    }
}