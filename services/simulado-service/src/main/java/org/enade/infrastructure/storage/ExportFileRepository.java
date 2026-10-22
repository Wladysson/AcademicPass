package org.enade.simulado.infrastructure.storage;

import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

@ApplicationScoped
public class ExportFileStorage {

    private static final Logger LOG =
            Logger.getLogger(ExportFileStorage.class);

    @ConfigProperty(name = "simulado.export.storage.type", defaultValue = "volume")
    String storageType;

    @ConfigProperty(
            name = "simulado.export.storage.path",
            defaultValue = "./data/exports"
    )
    String storagePath;

    @ConfigProperty(name = "simulado.export.storage.base-url", defaultValue = "")
    String baseUrl;

    public StoredExport salvar(
            String exportId,
            String fileName,
            byte[] content,
            String contentType
    ) {
        validar(exportId, fileName, content, contentType);

        if (!"volume".equalsIgnoreCase(storageType)) {
            throw new IllegalStateException(
                    "Tipo de armazenamento não suportado: " + storageType
            );
        }

        Path temporaryFile = null;

        try {
            Path root = Path.of(storagePath).toAbsolutePath().normalize();
            Path exportDirectory = root.resolve(exportId).normalize();

            if (!exportDirectory.startsWith(root)) {
                throw new IllegalArgumentException(
                        "Identificador de exportação inválido."
                );
            }

            Files.createDirectories(exportDirectory);

            Path destination = exportDirectory.resolve(fileName).normalize();

            if (!destination.startsWith(exportDirectory)) {
                throw new IllegalArgumentException(
                        "Nome de arquivo inválido."
                );
            }

            temporaryFile = Files.createTempFile(
                    exportDirectory,
                    "export-",
                    ".tmp"
            );

            Files.write(temporaryFile, content);

            try {
                Files.move(
                        temporaryFile,
                        destination,
                        StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING
                );
            } catch (IOException atomicMoveException) {
                Files.move(
                        temporaryFile,
                        destination,
                        StandardCopyOption.REPLACE_EXISTING
                );
            }

            String storageKey = exportId + "/" + fileName;
            String fileUrl = baseUrl.isBlank()
                    ? null
                    : baseUrl.replaceAll("/+$", "") + "/" + storageKey;

            LOG.infof(
                    "Arquivo de exportação armazenado: exportId=%s, storageKey=%s",
                    exportId,
                    storageKey
            );

            return new StoredExport(
                    storageKey,
                    destination.toString(),
                    fileUrl,
                    contentType,
                    content.length
            );
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Não foi possível armazenar o arquivo da exportação "
                            + exportId + ".",
                    exception
            );
        } finally {
            if (temporaryFile != null) {
                try {
                    Files.deleteIfExists(temporaryFile);
                } catch (IOException exception) {
                    LOG.warnf(
                            "Não foi possível remover o arquivo temporário: %s",
                            temporaryFile
                    );
                }
            }
        }
    }

    public byte[] ler(String storageKey) {
        if (storageKey == null || storageKey.isBlank()) {
            throw new IllegalArgumentException(
                    "A chave do arquivo é obrigatória."
            );
        }

        try {
            Path root = Path.of(storagePath).toAbsolutePath().normalize();
            Path file = root.resolve(storageKey).normalize();

            if (!file.startsWith(root)) {
                throw new IllegalArgumentException(
                        "Chave de armazenamento inválida."
                );
            }

            if (!Files.isRegularFile(file)) {
                throw new IllegalArgumentException(
                        "Arquivo de exportação não encontrado."
                );
            }

            return Files.readAllBytes(file);
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Não foi possível ler o arquivo de exportação.",
                    exception
            );
        }
    }

    public boolean excluir(String storageKey) {
        if (storageKey == null || storageKey.isBlank()) {
            throw new IllegalArgumentException(
                    "A chave do arquivo é obrigatória."
            );
        }

        try {
            Path root = Path.of(storagePath).toAbsolutePath().normalize();
            Path file = root.resolve(storageKey).normalize();

            if (!file.startsWith(root)) {
                throw new IllegalArgumentException(
                        "Chave de armazenamento inválida."
                );
            }

            return Files.deleteIfExists(file);
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Não foi possível excluir o arquivo de exportação.",
                    exception
            );
        }
    }

    private void validar(
            String exportId,
            String fileName,
            byte[] content,
            String contentType
    ) {
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

        if (fileName == null
                || fileName.isBlank()
                || fileName.contains("/")
                || fileName.contains("\\")
                || fileName.equals(".")
                || fileName.equals("..")) {
            throw new IllegalArgumentException(
                    "O nome do arquivo é inválido."
            );
        }

        if (content == null || content.length == 0) {
            throw new IllegalArgumentException(
                    "O conteúdo do arquivo não pode ser vazio."
            );
        }

        if (contentType == null || contentType.isBlank()) {
            throw new IllegalArgumentException(
                    "O tipo de conteúdo do arquivo é obrigatório."
            );
        }
    }

    public record StoredExport(
            String storageKey,
            String filePath,
            String fileUrl,
            String contentType,
            long size
    ) {
    }
}