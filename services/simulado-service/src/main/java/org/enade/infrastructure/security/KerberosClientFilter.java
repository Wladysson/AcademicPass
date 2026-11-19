package org.enade.simulado.infrastructure.security;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.client.ClientRequestContext;
import jakarta.ws.rs.client.ClientRequestFilter;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

@ApplicationScoped
public class KerberosClientFilter implements ClientRequestFilter {

    private static final Logger LOG =
            Logger.getLogger(KerberosClientFilter.class);

    @ConfigProperty(name = "simulado.kerberos.enabled", defaultValue = "false")
    boolean enabled;

    @ConfigProperty(name = "simulado.kerberos.principal", defaultValue = "")
    String principal;

    @ConfigProperty(name = "simulado.kerberos.service-name", defaultValue = "HTTP")
    String serviceName;

    @Override
    public void filter(ClientRequestContext requestContext) throws IOException {
        if (!enabled) {
            return;
        }

        String existingAuthorization =
                requestContext.getHeaderString(HttpHeaders.AUTHORIZATION);

        if (existingAuthorization != null && !existingAuthorization.isBlank()) {
            // Não substituir o token do usuário por credenciais internas.
            return;
        }

        String serviceToken = requestContext.getHeaderString("X-Service-Token");

        if (serviceToken != null && !serviceToken.isBlank()) {
            requestContext.getHeaders().putSingle(
                    HttpHeaders.AUTHORIZATION,
                    "Bearer " + serviceToken
            );
            return;
        }

        LOG.error(
                "Kerberos está habilitado, mas não há credencial de serviço configurada."
        );

        requestContext.abortWith(
                Response.status(Response.Status.UNAUTHORIZED)
                        .entity("{\"message\":\"Credenciais internas indisponíveis.\"}")
                        .type("application/json")
                        .build()
        );
    }

    public String criarServicePrincipalHeader() {
        if (principal == null || principal.isBlank()) {
            throw new IllegalStateException(
                    "O principal Kerberos não foi configurado."
            );
        }

        if (serviceName == null || serviceName.isBlank()) {
            throw new IllegalStateException(
                    "O nome do serviço Kerberos não foi configurado."
            );
        }

        String serviceIdentity = serviceName + "/" + principal;

        return "Negotiate " + Base64.getEncoder().encodeToString(
                serviceIdentity.getBytes(StandardCharsets.UTF_8)
        );
    }
}