package org.enade.search.infrastructure.redis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkus.redis.datasource.RedisDataSource;
import io.quarkus.redis.datasource.value.ValueCommands;
import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.enade.search.domain.exception.SearchException;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.domain.model.SearchResult;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;

@ApplicationScoped
public class SearchCacheRepository {

    private static final String CACHE_PREFIX = "academicpass:search:";
    private static final Duration DEFAULT_TTL = Duration.ofMinutes(5);

    private final ValueCommands<String, String> commands;
    private final ObjectMapper objectMapper;
    private final Duration ttl;

    public SearchCacheRepository(
            RedisDataSource redisDataSource,
            ObjectMapper objectMapper,
            @ConfigProperty(
                    name = "search.cache.ttl-seconds",
                    defaultValue = "300"
            ) long ttlSeconds
    ) {
        if (ttlSeconds < 1) {
            throw new IllegalArgumentException(
                    "O TTL do cache deve ser maior que zero."
            );
        }

        this.commands = redisDataSource.value(String.class);
        this.objectMapper = objectMapper;
        this.ttl = Duration.ofSeconds(ttlSeconds);
    }

    public SearchResult find(SearchFilter filter) {
        String key = buildKey(filter);

        try {
            String cachedValue = commands.get(key);

            if (cachedValue == null || cachedValue.isBlank()) {
                return null;
            }

            return objectMapper.readValue(
                    cachedValue,
                    SearchResult.class
            );
        } catch (JsonProcessingException exception) {
            invalidate(key);

            throw new SearchException(
                    "Não foi possível desserializar o resultado armazenado no cache.",
                    exception
            );
        } catch (RuntimeException exception) {
            if (exception instanceof SearchException searchException) {
                throw searchException;
            }

            throw new SearchException(
                    "Não foi possível consultar o cache Redis.",
                    exception
            );
        }
    }

    public void save(SearchFilter filter, SearchResult result) {
        if (result == null) {
            return;
        }

        String key = buildKey(filter);

        try {
            String serializedResult = objectMapper.writeValueAsString(result);

            commands.setex(
                    key,
                    ttl.toSeconds(),
                    serializedResult
            );
        } catch (JsonProcessingException exception) {
            throw new SearchException(
                    "Não foi possível serializar o resultado para o cache.",
                    exception
            );
        } catch (RuntimeException exception) {
            throw new SearchException(
                    "Não foi possível armazenar o resultado no cache Redis.",
                    exception
            );
        }
    }

    public void invalidate(SearchFilter filter) {
        invalidate(buildKey(filter));
    }

    private void invalidate(String key) {
        try {
            commands.getdel(key);
        } catch (RuntimeException exception) {
            throw new SearchException(
                    "Não foi possível invalidar a entrada do cache Redis.",
                    exception
            );
        }
    }

    private String buildKey(SearchFilter filter) {
        try {
            String canonicalFilter = objectMapper.writeValueAsString(filter);

            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(
                    canonicalFilter.getBytes(StandardCharsets.UTF_8)
            );

            return CACHE_PREFIX + HexFormat.of().formatHex(hash);
        } catch (JsonProcessingException | NoSuchAlgorithmException exception) {
            throw new SearchException(
                    "Não foi possível gerar a chave do cache de busca.",
                    exception
            );
        }
    }
}
