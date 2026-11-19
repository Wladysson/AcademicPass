package org.enade.search.infrastructure.identity;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.enade.search.domain.exception.SearchException;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;

@ApplicationScoped
public class IdentityTokenValidator {

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final String validationUrl;
    private final String serviceToken;

    public IdentityTokenValidator(
            ObjectMapper objectMapper,
            @ConfigProperty(
                    name = "identity.validation-url",
                    defaultValue = "http://localhost:8080/api/v1/auth/validate"
            ) String validationUrl,
            @ConfigProperty(
                    name = "identity.service-token",
                    defaultValue = ""
            ) String serviceToken
    ) {
        this.objectMapper = objectMapper;
        this.validationUrl = Objects.requireNonNull(validationUrl).trim();
        this.serviceToken = serviceToken == null ? "" : serviceToken.trim();
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    public ValidatedIdentity validate(String authorizationHeader) {
        if (authorizationHeader == null || authorizationHeader.isBlank()) {
            throw new SearchException("O token de autenticação é obrigatório.");
        }

        String token = extractBearerToken(authorizationHeader);

        try {
            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                    .uri(URI.create(validationUrl))
                    .timeout(Duration.ofSeconds(10))
                    .header("Authorization", "Bearer " + token)
                    .header("Accept", "application/json")
                    .GET();

            if (!serviceToken.isBlank()) {
                requestBuilder.header("X-Service-Token", serviceToken);
            }

            HttpResponse<String> response = httpClient.send(
                    requestBuilder.build(),
                    HttpResponse.BodyHandlers.ofString()
            );

            if (response.statusCode() == 401 || response.statusCode() == 403) {
                throw new SearchException("O token de autenticação é inválido ou não autorizado.");
            }

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new SearchException("O serviço de identidade não conseguiu validar o token.");
            }

            JsonNode body = objectMapper.readTree(response.body());

            if (!body.path("valid").asBoolean(false)) {
                throw new SearchException("O token de autenticação é inválido ou expirou.");
            }

            String subject = textOrNull(body, "sub");
            String role = textOrNull(body, "role");
            String sessionId = textOrNull(body, "sessionId");

            if (subject == null || role == null) {
                throw new SearchException("A resposta do serviço de identidade não contém os dados obrigatórios.");
            }

            return new ValidatedIdentity(subject, role, sessionId);

        } catch (SearchException exception) {
            throw exception;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new SearchException("A validação do token foi interrompida.", exception);
        } catch (Exception exception) {
            throw new SearchException("Não foi possível validar o token no serviço de identidade.", exception);
        }
    }

    private String extractBearerToken(String authorizationHeader) {
        String trimmedHeader = authorizationHeader.trim();

        if (!trimmedHeader.regionMatches(true, 0, "Bearer ", 0, 7)) {
            throw new SearchException("O cabeçalho Authorization deve utilizar o esquema Bearer.");
        }

        String token = trimmedHeader.substring(7).trim();

        if (token.isBlank() || token.contains(" ")) {
            throw new SearchException("O token de autenticação possui formato inválido.");
        }

        return token;
    }

    private String textOrNull(JsonNode node, String field) {
        JsonNode value = node.get(field);

        if (value == null || value.isNull() || !value.isValueNode()) {
            return null;
        }

        String text = value.asText();

        return text.isBlank() ? null : text;
    }

    public record ValidatedIdentity(
            String subject,
            String role,
            String sessionId
    ) {
    }
}