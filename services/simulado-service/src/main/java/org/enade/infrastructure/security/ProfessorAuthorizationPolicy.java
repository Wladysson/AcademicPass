package org.enade.simulado.infrastructure.security;

import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.infrastructure.identity.IdentityTokenValidator;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Locale;

@ApplicationScoped
public class ProfessorAuthorizationPolicy {

    private static final Logger LOG =
            Logger.getLogger(ProfessorAuthorizationPolicy.class);

    @Inject
    IdentityTokenValidator identityTokenValidator;

    @Inject
    ObjectMapper objectMapper;

    @ConfigProperty(name = "simulado.identity.base-url")
    String identityBaseUrl;

    @ConfigProperty(
            name = "simulado.identity.session-path",
            defaultValue = "/api/v1/auth/session"
    )
    String sessionPath;

    @ConfigProperty(
            name = "simulado.identity.timeout-seconds",
            defaultValue = "5"
    )
    long timeoutSeconds;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    public void validarProfessor(String authorizationHeader) {
        if (authorizationHeader == null || authorizationHeader.isBlank()) {
            throw new SimuladoExportException(
                    "O cabeçalho Authorization é obrigatório."
            );
        }

        if (!identityTokenValidator.validar(authorizationHeader)) {
            throw new SimuladoExportException(
                    "Token inválido ou sessão não autorizada."
            );
        }

        JsonNode session = consultarSessao(authorizationHeader);

        if (!possuiPapelProfessor(session)) {
            LOG.warn("Tentativa de exportação sem permissão de PROFESSOR.");

            throw new SimuladoExportException(
                    "Apenas usuários com o papel PROFESSOR podem exportar simulados."
            );
        }
    }

    private JsonNode consultarSessao(String authorizationHeader) {
        if (timeoutSeconds <= 0) {
            throw new IllegalStateException(
                    "O timeout do identity-service deve ser maior que zero."
            );
        }

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(normalizarBaseUrl() + normalizarPath()))
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .header("Accept", "application/json")
                    .header("Authorization", authorizationHeader)
                    .GET()
                    .build();

            HttpResponse<String> response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString()
            );

            if (response.statusCode() == 401 || response.statusCode() == 403) {
                throw new SimuladoExportException(
                        "A sessão não possui autorização para exportar simulados."
                );
            }

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new SimuladoExportException(
                        "Não foi possível consultar os papéis do usuário."
                );
            }

            if (response.body() == null || response.body().isBlank()) {
                throw new SimuladoExportException(
                        "O identity-service retornou uma sessão vazia."
                );
            }

            return objectMapper.readTree(response.body());

        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();

            throw new SimuladoExportException(
                    "A consulta à sessão do usuário foi interrompida.",
                    exception
            );
        } catch (IOException | IllegalArgumentException exception) {
            throw new SimuladoExportException(
                    "Não foi possível verificar as permissões do usuário.",
                    exception
            );
        }
    }

    private boolean possuiPapelProfessor(JsonNode session) {
        if (session == null || session.isNull()) {
            return false;
        }

        JsonNode roles = session.has("roles")
                ? session.get("roles")
                : session.path("user").path("roles");

        if (roles.isArray()) {
            for (JsonNode role : roles) {
                if (role.isTextual() && ehProfessor(role.asText())) {
                    return true;
                }

                if (role.isObject()) {
                    JsonNode name = role.has("name")
                            ? role.get("name")
                            : role.get("role");

                    if (name != null
                            && name.isTextual()
                            && ehProfessor(name.asText())) {
                        return true;
                    }
                }
            }

            return false;
        }

        if (roles.isTextual()) {
            return ehProfessor(roles.asText());
        }

        JsonNode role = session.has("role")
                ? session.get("role")
                : session.path("user").path("role");

        return role.isTextual() && ehProfessor(role.asText());
    }

    private boolean ehProfessor(String role) {
        return "PROFESSOR".equals(
                role.trim().toUpperCase(Locale.ROOT)
        );
    }

    private String normalizarBaseUrl() {
        if (identityBaseUrl == null || identityBaseUrl.isBlank()) {
            throw new IllegalStateException(
                    "A URL do identity-service não foi configurada."
            );
        }

        return identityBaseUrl.replaceAll("/+$", "");
    }

    private String normalizarPath() {
        if (sessionPath == null || sessionPath.isBlank()) {
            throw new IllegalStateException(
                    "O endpoint de consulta de sessão não foi configurado."
            );
        }

        return sessionPath.startsWith("/")
                ? sessionPath
                : "/" + sessionPath;
    }
}