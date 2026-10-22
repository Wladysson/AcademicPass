package org.enade.simulado.infrastructure.redis;

import org.enade.simulado.domain.model.ExportStatus;
import org.enade.simulado.domain.exception.SimuladoExportException;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;
import io.quarkus.redis.datasource.RedisDataSource;
import io.quarkus.redis.datasource.value.ValueCommands;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

@ApplicationScoped
public class ExportStatusRepository {

    private static final Logger LOG =
            Logger.getLogger(ExportStatusRepository.class);

    private static final String KEY_PREFIX = "simulado:export:status:";

    @Inject
    RedisDataSource redisDataSource;

    @ConfigProperty(
            name = "simulado.export.status.ttl-seconds",
            defaultValue = "86400"
    )
    long ttlSeconds;

    private ValueCommands<String, ExportStatusRecord> commands;

    @jakarta.annotation.PostConstruct
    void inicializar() {
        commands = redisDataSource.value(ExportStatusRecord.class);
    }

    public void salvar(
            String exportId,
            ExportStatus status,
            String message,
            Instant updatedAt
    ) {
        validarExportId(exportId);

        if (status == null || updatedAt == null) {
            throw new IllegalArgumentException(
                    "O status e a data de atualização são obrigatórios."
            );
        }

        if (ttlSeconds <= 0) {
            throw new IllegalStateException(
                    "O TTL dos status de exportação deve ser maior que zero."
            );
        }

        ExportStatusRecord record = new ExportStatusRecord(
                exportId,
                status,
                message,
                updatedAt.toString()
        );

        try {
            commands.setex(chave(exportId), ttlSeconds, record);
            LOG.debugf(
                    "Status da exportação atualizado: exportId=%s, status=%s",
                    exportId,
                    status
            );
        } catch (RuntimeException exception) {
            LOG.errorf(
                    exception,
                    "Falha ao salvar o status da exportação %s",
                    exportId
            );

            throw new SimuladoExportException(
                    "Não foi possível salvar o status da exportação.",
                    exception
            );
        }
    }

    public Optional<ExportStatusRecord> buscar(String exportId) {
        validarExportId(exportId);

        try {
            return Optional.ofNullable(commands.get(chave(exportId)));
        } catch (RuntimeException exception) {
            LOG.errorf(
                    exception,
                    "Falha ao consultar o status da exportação %s",
                    exportId
            );

            throw new SimuladoExportException(
                    "Não foi possível consultar o status da exportação.",
                    exception
            );
        }
    }

    public void atualizarStatus(
            String exportId,
            ExportStatus novoStatus,
            String message,
            Instant updatedAt
    ) {
        ExportStatusRecord atual = buscar(exportId)
                .orElseThrow(() -> new SimuladoExportException(
                        "Não existe registro para a exportação " + exportId + "."
                ));

        if (!atual.status().canTransitionTo(novoStatus)) {
            throw new SimuladoExportException(
                    "Transição de status inválida: "
                            + atual.status() + " -> " + novoStatus
            );
        }

        salvar(exportId, novoStatus, message, updatedAt);
    }

    public boolean excluir(String exportId) {
        validarExportId(exportId);

        try {
            return redisDataSource.key().del(chave(exportId)) > 0;
        } catch (RuntimeException exception) {
            LOG.errorf(
                    exception,
                    "Falha ao excluir o status da exportação %s",
                    exportId
            );

            throw new SimuladoExportException(
                    "Não foi possível excluir o status da exportação.",
                    exception
            );
        }
    }

    private String chave(String exportId) {
        return KEY_PREFIX + exportId;
    }

    private void validarExportId(String exportId) {
        if (exportId == null || exportId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da exportação é obrigatório."
            );
        }

        try {
            UUID.fromString(exportId);
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException(
                    "O identificador da exportação deve ser um UUID válido.",
                    exception
            );
        }
    }

    public record ExportStatusRecord(
            String exportId,
            ExportStatus status,
            String message,
            String updatedAt
    ) {
    }
}