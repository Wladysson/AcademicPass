package org.enade.identity.infrastructure.ldap;

import org.enade.identity.domain.exception.InvalidCredentialsException;
import org.enade.identity.domain.model.UserAccount;
import org.enade.identity.domain.model.UserRole;

import jakarta.enterprise.context.ApplicationScoped;

import javax.naming.AuthenticationException;
import javax.naming.Context;
import javax.naming.NamingEnumeration;
import javax.naming.NamingException;
import javax.naming.directory.Attribute;
import javax.naming.directory.Attributes;
import javax.naming.directory.DirContext;
import javax.naming.directory.InitialDirContext;
import javax.naming.directory.SearchControls;
import javax.naming.directory.SearchResult;
import java.nio.charset.StandardCharsets;
import java.util.Hashtable;
import java.util.UUID;

@ApplicationScoped
public class LdapAuthenticationRepository {

    private static final String LDAP_URL = "LDAP_URL";
    private static final String LDAP_BASE_DN = "LDAP_BASE_DN";
    private static final String LDAP_BIND_DN = "LDAP_BIND_DN";
    private static final String LDAP_BIND_PASSWORD = "LDAP_BIND_PASSWORD";

    private static final String DEFAULT_USERNAME_ATTRIBUTE = "uid";
    private static final String DEFAULT_DISPLAY_NAME_ATTRIBUTE = "displayName";
    private static final String DEFAULT_EMAIL_ATTRIBUTE = "mail";
    private static final String DEFAULT_ROLE_ATTRIBUTE = "enadeRole";

    public UserAccount authenticate(String username, String password) {
        validateCredentials(username, password);

        String normalizedUsername = username.trim();
        LdapConfiguration configuration = loadConfiguration();

        LdapUser ldapUser = findUser(normalizedUsername, configuration);

        if (ldapUser == null || !ldapUser.active()) {
            throw new InvalidCredentialsException();
        }

        authenticateUserDn(ldapUser.dn(), password, configuration);

        return new UserAccount(
                UUID.nameUUIDFromBytes(
                        ldapUser.dn().getBytes(StandardCharsets.UTF_8)
                ),
                ldapUser.username(),
                ldapUser.displayName(),
                ldapUser.email(),
                ldapUser.role(),
                true
        );
    }

    private LdapUser findUser(
            String username,
            LdapConfiguration configuration) {

        Hashtable<String, String> environment =
                createEnvironment(configuration);

        environment.put(Context.SECURITY_AUTHENTICATION, "simple");
        environment.put(
                Context.SECURITY_PRINCIPAL,
                configuration.bindDn()
        );
        environment.put(
                Context.SECURITY_CREDENTIALS,
                configuration.bindPassword()
        );

        try (DirContext context = new InitialDirContext(environment)) {
            SearchControls controls = new SearchControls();
            controls.setSearchScope(SearchControls.SUBTREE_SCOPE);
            controls.setCountLimit(2);
            controls.setReturningObjFlag(false);

            controls.setReturningAttributes(new String[]{
                    configuration.usernameAttribute(),
                    configuration.displayNameAttribute(),
                    configuration.emailAttribute(),
                    configuration.roleAttribute(),
                    configuration.activeAttribute()
            });

            String filter = "("
                    + configuration.usernameAttribute()
                    + "="
                    + escapeLdapFilter(username)
                    + ")";

            try (NamingEnumeration<SearchResult> results =
                         context.search(
                                 configuration.baseDn(),
                                 filter,
                                 controls
                         )) {

                if (!results.hasMore()) {
                    return null;
                }

                SearchResult result = results.next();

                if (results.hasMore()) {
                    throw new IllegalStateException(
                            "O LDAP retornou múltiplas contas para o usuário informado."
                    );
                }

                return mapUser(
                        result,
                        configuration
                );
            }
        } catch (NamingException exception) {
            throw new IllegalStateException(
                    "Não foi possível consultar o diretório LDAP.",
                    exception
            );
        }
    }

    private LdapUser mapUser(
            SearchResult result,
            LdapConfiguration configuration) throws NamingException {

        Attributes attributes = result.getAttributes();

        String username = requiredAttribute(
                attributes,
                configuration.usernameAttribute()
        );

        String displayName = optionalAttribute(
                attributes,
                configuration.displayNameAttribute()
        );

        String email = optionalAttribute(
                attributes,
                configuration.emailAttribute()
        );

        String roleValue = requiredAttribute(
                attributes,
                configuration.roleAttribute()
        );

        UserRole role;

        try {
            role = UserRole.fromLdapValue(roleValue);
        } catch (IllegalArgumentException exception) {
            throw new IllegalStateException(
                    "O usuário possui um papel LDAP inválido.",
                    exception
            );
        }

        String activeAttribute = configuration.activeAttribute();
        boolean active = true;

        if (!activeAttribute.isBlank()) {
            String activeValue = optionalAttribute(
                    attributes,
                    activeAttribute
            );

            active = parseActiveStatus(activeValue);
        }

        String userDn = result.getNameInNamespace();

        if (userDn == null || userDn.isBlank()) {
            throw new IllegalStateException(
                    "O LDAP não retornou o identificador da conta."
            );
        }

        return new LdapUser(
                userDn,
                username,
                displayName,
                email,
                role,
                active
        );
    }

    private void authenticateUserDn(
            String userDn,
            String password,
            LdapConfiguration configuration) {

        Hashtable<String, String> environment =
                createEnvironment(configuration);

        environment.put(Context.SECURITY_AUTHENTICATION, "simple");
        environment.put(Context.SECURITY_PRINCIPAL, userDn);
        environment.put(Context.SECURITY_CREDENTIALS, password);

        try (DirContext ignored = new InitialDirContext(environment)) {
            // A conexão autenticada confirma as credenciais do usuário.
        } catch (AuthenticationException exception) {
            throw new InvalidCredentialsException();
        } catch (NamingException exception) {
            throw new IllegalStateException(
                    "Não foi possível validar as credenciais no LDAP.",
                    exception
            );
        }
    }

    private Hashtable<String, String> createEnvironment(
            LdapConfiguration configuration) {

        Hashtable<String, String> environment = new Hashtable<>();

        environment.put(
                Context.INITIAL_CONTEXT_FACTORY,
                "com.sun.jndi.ldap.LdapCtxFactory"
        );
        environment.put(
                Context.PROVIDER_URL,
                configuration.url()
        );
        environment.put(
                Context.REFERRAL,
                "throw"
        );
        environment.put(
                "com.sun.jndi.ldap.connect.timeout",
                "5000"
        );
        environment.put(
                "com.sun.jndi.ldap.read.timeout",
                "5000"
        );

        return environment;
    }

    private LdapConfiguration loadConfiguration() {
        String url = requiredEnvironment(LDAP_URL);
        String baseDn = requiredEnvironment(LDAP_BASE_DN);
        String bindDn = requiredEnvironment(LDAP_BIND_DN);
        String bindPassword = requiredEnvironment(LDAP_BIND_PASSWORD);

        if (!url.startsWith("ldaps://") && !url.startsWith("ldap://")) {
            throw new IllegalStateException(
                    "LDAP_URL deve utilizar o protocolo ldap:// ou ldaps://."
            );
        }

        if (url.startsWith("ldap://")
                && !Boolean.parseBoolean(
                System.getenv().getOrDefault(
                        "LDAP_ALLOW_INSECURE",
                        "false"
                )
        )) {
            throw new IllegalStateException(
                    "LDAP sem TLS está desabilitado. Configure LDAPS ou "
                            + "habilite explicitamente LDAP_ALLOW_INSECURE "
                            + "apenas em ambientes isolados de desenvolvimento."
            );
        }

        String usernameAttribute = environmentOrDefault(
                "LDAP_USERNAME_ATTRIBUTE",
                DEFAULT_USERNAME_ATTRIBUTE
        );

        String displayNameAttribute = environmentOrDefault(
                "LDAP_DISPLAY_NAME_ATTRIBUTE",
                DEFAULT_DISPLAY_NAME_ATTRIBUTE
        );

        String emailAttribute = environmentOrDefault(
                "LDAP_EMAIL_ATTRIBUTE",
                DEFAULT_EMAIL_ATTRIBUTE
        );

        String roleAttribute = environmentOrDefault(
                "LDAP_ROLE_ATTRIBUTE",
                DEFAULT_ROLE_ATTRIBUTE
        );

        String activeAttribute = environmentOrDefault(
                "LDAP_ACTIVE_ATTRIBUTE",
                ""
        );

        validateAttributeName(usernameAttribute);
        validateAttributeName(displayNameAttribute);
        validateAttributeName(emailAttribute);
        validateAttributeName(roleAttribute);

        if (!activeAttribute.isBlank()) {
            validateAttributeName(activeAttribute);
        }

        return new LdapConfiguration(
                url,
                baseDn,
                bindDn,
                bindPassword,
                usernameAttribute,
                displayNameAttribute,
                emailAttribute,
                roleAttribute,
                activeAttribute
        );
    }

    private String requiredEnvironment(String name) {
        String value = System.getenv(name);

        if (value == null || value.isBlank()) {
            throw new IllegalStateException(
                    "A variável de ambiente obrigatória "
                            + name
                            + " não está configurada."
            );
        }

        return value.trim();
    }

    private String environmentOrDefault(String name, String defaultValue) {
        String value = System.getenv(name);

        return value == null || value.isBlank()
                ? defaultValue
                : value.trim();
    }

    private String requiredAttribute(
            Attributes attributes,
            String attributeName) throws NamingException {

        String value = optionalAttribute(attributes, attributeName);

        if (value.isBlank()) {
            throw new IllegalStateException(
                    "O LDAP não retornou o atributo obrigatório "
                            + attributeName
                            + "."
            );
        }

        return value;
    }

    private String optionalAttribute(
            Attributes attributes,
            String attributeName) throws NamingException {

        if (attributeName == null || attributeName.isBlank()) {
            return "";
        }

        Attribute attribute = attributes.get(attributeName);

        if (attribute == null || attribute.get() == null) {
            return "";
        }

        return attribute.get().toString().trim();
    }

    private boolean parseActiveStatus(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }

        return switch (value.trim().toLowerCase()) {
            case "true", "active", "enabled", "1" -> true;
            case "false", "inactive", "disabled", "0" -> false;
            default -> false;
        };
    }

    private String escapeLdapFilter(String value) {
        StringBuilder escaped = new StringBuilder();

        for (char character : value.toCharArray()) {
            switch (character) {
                case '\\' -> escaped.append("\\5c");
                case '*' -> escaped.append("\\2a");
                case '(' -> escaped.append("\\28");
                case ')' -> escaped.append("\\29");
                case '\0' -> escaped.append("\\00");
                default -> escaped.append(character);
            }
        }

        return escaped.toString();
    }

    private void validateAttributeName(String attributeName) {
        if (attributeName == null
                || !attributeName.matches("[a-zA-Z][a-zA-Z0-9;-]*")) {
            throw new IllegalStateException(
                    "Nome de atributo LDAP inválido na configuração."
            );
        }
    }

    private void validateCredentials(String username, String password) {
        if (username == null
                || username.isBlank()
                || password == null
                || password.isBlank()) {
            throw new InvalidCredentialsException();
        }
    }

    private record LdapConfiguration(
            String url,
            String baseDn,
            String bindDn,
            String bindPassword,
            String usernameAttribute,
            String displayNameAttribute,
            String emailAttribute,
            String roleAttribute,
            String activeAttribute) {
    }

    private record LdapUser(
            String dn,
            String username,
            String displayName,
            String email,
            UserRole role,
            boolean active) {
    }
}
