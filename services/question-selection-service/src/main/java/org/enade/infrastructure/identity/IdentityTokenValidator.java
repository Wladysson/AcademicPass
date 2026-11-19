package org.enade.selection.infrastructure.identity;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.enade.selection.domain.exception.SelectionException;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class IdentityTokenValidator {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String validationUrl;

    @Inject
    public IdentityTokenValidator(
            ObjectMapper objectMapper,
            @ConfigProperty(
                    name = "identity.validation.url",
                    defaultValue = "http://localhost:8080/api/v1/auth/validate"
            ) String validationUrl
    ) {
        this.objectMapper = objectMapper;
        this.validationUrl = validationUrl;

        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
    }

    public String validateAndGetUserId(String token) {
        if (token == null || token.isBlank()) {
            throw new SelectionException(
                    "O token de autenticação é obrigatório."
            );
        }

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(validationUrl))
                .timeout(Duration.ofSeconds(10))
                .header("Authorization", "Bearer " + token)
                .header("Accept", "application/json")
                .GET()
                .build();

        try {
            HttpResponse<String> response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString()
            );

            if (response.statusCode() == 401
                    || response.statusCode() == 403) {
                throw new SelectionException(
                        "O token de autenticação é inválido ou expirou."
                );
            }

            if (response.statusCode() < 200
                    || response.statusCode() >= 300) {
                throw new SelectionException(
                        "Não foi possível validar o token no identity-service."
                );
            }

            JsonNode body = objectMapper.readTree(response.body());

            if (body == null || !body.path("active").asBoolean(false)) {
                throw new SelectionException(
                        "O token de autenticação não está ativo."
                );
            }

            String userId = body.path("userId").asText(null);

            if (userId == null || userId.isBlank()) {
                throw new SelectionException(
                        "O identity-service não retornou o identificador do usuário."
                );
            }

            return userId.trim();

        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();

            throw new SelectionException(
                    "A validação do token foi interrompida.",
                    exception
            );
        } catch (IOException | IllegalArgumentException exception) {
            throw new SelectionException(
                    "Falha de comunicação com o identity-service.",
                    exception
            );
        }
    }
}