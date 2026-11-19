package org.enade.identity.infrastructure.security;

import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import jakarta.ws.rs.ext.Provider;

import javax.security.auth.Subject;
import javax.security.auth.login.AppConfigurationEntry;
import javax.security.auth.login.Configuration;
import javax.security.auth.login.LoginContext;
import javax.security.auth.login.LoginException;
import org.ietf.jgss.GSSContext;
import org.ietf.jgss.GSSCredential;
import org.ietf.jgss.GSSException;
import org.ietf.jgss.GSSManager;
import org.ietf.jgss.GSSName;
import org.ietf.jgss.Oid;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.PrivilegedExceptionAction;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

@Provider
@ApplicationScoped
@Priority(Priorities.AUTHENTICATION)
public class KerberosServerFilter implements ContainerRequestFilter {

    private static final String NEGOTIATE_PREFIX = "Negotiate ";
    private static final String SPNEGO_OID_VALUE = "1.3.6.1.5.5.2";
    private static final String JAAS_CONTEXT = "EnadeKerberosAcceptor";

    private volatile Subject serviceSubject;
    private volatile GSSCredential acceptorCredential;

    @Override
    public void filter(ContainerRequestContext requestContext)
            throws IOException {

        if (!isKerberosEnabled()
                || !isProtectedPath(requestContext)) {
            return;
        }

        String authorization = requestContext.getHeaderString(
                HttpHeaders.AUTHORIZATION
        );

        if (authorization == null
                || !authorization.startsWith(NEGOTIATE_PREFIX)) {
            reject(requestContext);
            return;
        }

        String encodedToken = authorization
                .substring(NEGOTIATE_PREFIX.length())
                .trim();

        if (encodedToken.isBlank()) {
            reject(requestContext);
            return;
        }

        try {
            byte[] token = Base64.getDecoder().decode(encodedToken);

            if (token.length == 0) {
                reject(requestContext);
                return;
            }

            GSSContext context = acceptToken(token);

            try {
                if (!context.isEstablished()) {
                    reject(requestContext);
                    return;
                }

                GSSName clientName = context.getSrcName();

                if (clientName == null) {
                    reject(requestContext);
                    return;
                }

                String principal = clientName.toString();

                requestContext.setSecurityContext(
                        new KerberosSecurityContext(
                                principal,
                                requestContext.getSecurityContext().isSecure()
                        )
                );
            } finally {
                context.dispose();
            }
        } catch (IllegalArgumentException | GSSException exception) {
            reject(requestContext);
        } catch (LoginException exception) {
            serviceUnavailable(requestContext);
        } catch (Exception exception) {
            serviceUnavailable(requestContext);
        }
    }

    private boolean isKerberosEnabled() {
        return Boolean.parseBoolean(
                System.getenv().getOrDefault(
                        "KERBEROS_ENABLED",
                        "false"
                )
        );
    }

    private boolean isProtectedPath(
            ContainerRequestContext requestContext) {

        String configuredPrefix = System.getenv().getOrDefault(
                "KERBEROS_PROTECTED_PATH_PREFIX",
                "/internal/"
        );

        String prefix = configuredPrefix.trim();

        if (prefix.isBlank()) {
            return false;
        }

        if (!prefix.startsWith("/")) {
            prefix = "/" + prefix;
        }

        if (!prefix.endsWith("/")) {
            prefix = prefix + "/";
        }

        String path = "/" + requestContext.getUriInfo()
                .getPath()
                .replaceAll("^/+", "");

        return path.startsWith(prefix);
    }

    private GSSContext acceptToken(byte[] token) throws Exception {
        Subject subject = getServiceSubject();

        return Subject.doAs(
                subject,
                (PrivilegedExceptionAction<GSSContext>) () -> {
                    GSSManager manager = GSSManager.getInstance();

                    GSSCredential credential = getAcceptorCredential(manager);

                    GSSContext context = manager.createContext(credential);

                    try {
                        context.acceptSecContext(token, 0, token.length);
                        return context;
                    } catch (GSSException exception) {
                        context.dispose();
                        throw exception;
                    }
                }
        );
    }

    private Subject getServiceSubject() throws LoginException {
        if (serviceSubject != null) {
            return serviceSubject;
        }

        synchronized (this) {
            if (serviceSubject != null) {
                return serviceSubject;
            }

            String principal = requiredEnvironment(
                    "KERBEROS_SERVICE_PRINCIPAL"
            );

            String keytab = requiredEnvironment(
                    "KERBEROS_KEYTAB"
            );

            Map<String, String> options = new HashMap<>();
            options.put("principal", principal);
            options.put("keyTab", keytab);
            options.put("useKeyTab", "true");
            options.put("storeKey", "true");
            options.put("doNotPrompt", "true");
            options.put("isInitiator", "false");
            options.put("refreshKrb5Config", "true");

            AppConfigurationEntry entry = new AppConfigurationEntry(
                    "com.sun.security.auth.module.Krb5LoginModule",
                    AppConfigurationEntry.LoginModuleControlFlag.REQUIRED,
                    options
            );

            Configuration configuration = new Configuration() {
                @Override
                public AppConfigurationEntry[] getAppConfigurationEntry(
                        String name) {

                    if (!JAAS_CONTEXT.equals(name)) {
                        return null;
                    }

                    return new AppConfigurationEntry[]{entry};
                }
            };

            LoginContext loginContext = new LoginContext(
                    JAAS_CONTEXT,
                    null,
                    null,
                    configuration
            );

            loginContext.login();
            serviceSubject = loginContext.getSubject();

            return serviceSubject;
        }
    }

    private GSSCredential getAcceptorCredential(
            GSSManager manager) throws GSSException {

        if (acceptorCredential != null) {
            return acceptorCredential;
        }

        synchronized (this) {
            if (acceptorCredential == null) {
                Oid spnegoOid = new Oid(SPNEGO_OID_VALUE);

                acceptorCredential = manager.createCredential(
                        null,
                        GSSCredential.INDEFINITE_LIFETIME,
                        spnegoOid,
                        GSSCredential.ACCEPT_ONLY
                );
            }

            return acceptorCredential;
        }
    }

    private String requiredEnvironment(String name) {
        String value = System.getenv(name);

        if (value == null || value.isBlank()) {
            throw new IllegalStateException(
                    "A variável obrigatória " + name
                            + " não está configurada."
            );
        }

        return value.trim();
    }

    private void reject(ContainerRequestContext requestContext) {
        requestContext.abortWith(
                Response.status(Response.Status.UNAUTHORIZED)
                        .header(HttpHeaders.WWW_AUTHENTICATE, "Negotiate")
                        .entity(Map.of(
                                "code", "KERBEROS_AUTHENTICATION_REQUIRED",
                                "message",
                                "Autenticação Kerberos obrigatória para este recurso."
                        ))
                        .type("application/json")
                        .build()
        );
    }

    private void serviceUnavailable(
            ContainerRequestContext requestContext) {

        requestContext.abortWith(
                Response.status(Response.Status.SERVICE_UNAVAILABLE)
                        .entity(Map.of(
                                "code", "KERBEROS_UNAVAILABLE",
                                "message",
                                "Não foi possível validar a autenticação Kerberos."
                        ))
                        .type("application/json")
                        .build()
        );
    }

    private static final class KerberosSecurityContext
            implements SecurityContext {

        private final String principal;
        private final boolean secure;

        private KerberosSecurityContext(
                String principal,
                boolean secure) {
            this.principal = principal;
            this.secure = secure;
        }

        @Override
        public java.security.Principal getUserPrincipal() {
            return () -> principal;
        }

        @Override
        public boolean isUserInRole(String role) {
            // Kerberos autentica a identidade; papéis são definidos pela aplicação.
            return false;
        }

        @Override
        public boolean isSecure() {
            return secure;
        }

        @Override
        public String getAuthenticationScheme() {
            return "KERBEROS";
        }
    }
}
