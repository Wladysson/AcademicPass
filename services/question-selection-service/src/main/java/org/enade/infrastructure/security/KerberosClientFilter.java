package org.enade.selection.infrastructure.security;

import java.io.IOException;
import java.net.Authenticator;
import java.net.PasswordAuthentication;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Base64;

import org.eclipse.microprofile.config.inject.ConfigProperty;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.client.ClientRequestContext;
import jakarta.ws.rs.client.ClientRequestFilter;
import jakarta.ws.rs.ext.Provider;

@Provider
@ApplicationScoped
public class KerberosClientFilter implements ClientRequestFilter {

    private final boolean enabled;
    private final String servicePrincipal;

    public KerberosClientFilter(
            @ConfigProperty(
                    name = "kerberos.client.enabled",
                    defaultValue = "false"
            ) boolean enabled,
            @ConfigProperty(
                    name = "kerberos.client.service-principal",
                    defaultValue = ""
            ) String servicePrincipal
    ) {
        this.enabled = enabled;
        this.servicePrincipal = servicePrincipal;
    }

    @Override
    public void filter(ClientRequestContext requestContext)
            throws IOException {

        if (!enabled) {
            return;
        }

        if (servicePrincipal == null || servicePrincipal.isBlank()) {
            throw new IOException(
                    "O principal de serviço Kerberos não foi configurado."
            );
        }

        String authorization = requestContext.getHeaderString("Authorization");

        if (authorization != null && !authorization.isBlank()) {
            return;
        }

        String token = System.getProperty("javax.security.auth.useSubjectCredsOnly");

        if (token == null) {
            throw new IOException(
                    "Kerberos está habilitado, mas as credenciais GSSAPI não foram configuradas na JVM."
            );
        }

        requestContext.getHeaders().putSingle(
                "X-Kerberos-Service-Principal",
                servicePrincipal
        );
    }
}