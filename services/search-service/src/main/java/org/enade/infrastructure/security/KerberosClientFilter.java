package org.enade.search.infrastructure.security;

import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.client.ClientRequestContext;
import jakarta.ws.rs.client.ClientRequestFilter;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.MultivaluedMap;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.io.IOException;
import java.util.Base64;

@ApplicationScoped
@Priority(Priorities.AUTHENTICATION)
public class KerberosClientFilter implements ClientRequestFilter {

    private final boolean enabled;
    private final String servicePrincipal;
    private final String servicePassword;

    public KerberosClientFilter(
            @ConfigProperty(
                    name = "identity.kerberos.enabled",
                    defaultValue = "false"
            ) boolean enabled,
            @ConfigProperty(
                    name = "identity.kerberos.service-principal",
                    defaultValue = ""
            ) String servicePrincipal,
            @ConfigProperty(
                    name = "identity.kerberos.service-password",
                    defaultValue = ""
            ) String servicePassword
    ) {
        this.enabled = enabled;
        this.servicePrincipal = servicePrincipal == null
                ? ""
                : servicePrincipal.trim();
        this.servicePassword = servicePassword == null
                ? ""
                : servicePassword;
    }

    @Override
    public void filter(ClientRequestContext requestContext) throws IOException {
        if (!enabled) {
            return;
        }

        if (servicePrincipal.isBlank() || servicePassword.isBlank()) {
            throw new IOException(
                    "As credenciais do serviço para autenticação Kerberos não foram configuradas."
            );
        }

        MultivaluedMap<String, Object> headers = requestContext.getHeaders();

        if (headers.containsKey(HttpHeaders.AUTHORIZATION)) {
            return;
        }

        String credentials = servicePrincipal + ":" + servicePassword;
        String encodedCredentials = Base64.getEncoder().encodeToString(
                credentials.getBytes(java.nio.charset.StandardCharsets.UTF_8)
        );

        headers.putSingle(
                HttpHeaders.AUTHORIZATION,
                "Basic " + encodedCredentials
        );
    }
}
