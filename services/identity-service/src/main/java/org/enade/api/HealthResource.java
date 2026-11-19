package org.enade.identity.api;

import org.enade.identity.infrastructure.redis.SessionRepository;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@Path("/health")
@Produces(MediaType.APPLICATION_JSON)
public class HealthResource {

    @Inject
    SessionRepository sessionRepository;

    @GET
    @Path("/live")
    public Response liveness() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("status", "UP");
        response.put("service", "identity-service");
        response.put("check", "liveness");
        response.put("timestamp", Instant.now().toString());

        return Response.ok(response).build();
    }

    @GET
    @Path("/ready")
    public Response readiness() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("service", "identity-service");
        response.put("check", "readiness");
        response.put("timestamp", Instant.now().toString());

        try {
            sessionRepository.checkAvailability();

            response.put("status", "UP");
            response.put("dependencies", Map.of(
                    "redis", "UP"
            ));

            return Response.ok(response).build();
        } catch (Exception exception) {
            response.put("status", "DOWN");
            response.put("dependencies", Map.of(
                    "redis", "DOWN"
            ));

            return Response.status(Response.Status.SERVICE_UNAVAILABLE)
                    .entity(response)
                    .build();
        }
    }
}
