/**
 * ntwebsrv_client.java - Java client for ntwebsrv (Automation Agent)
 * 
 * Requires: Java 11+ (uses HttpClient), Gson library
 * Compile: javac -cp gson-2.10.1.jar ntwebsrv_client.java
 * Run: java -cp .:gson-2.10.1.jar ntwebsrv_client [options] <json-file>
 * 
 * Supports three modes:
 *   1. LEGACY UPLOAD (multipart) - POST /ricevi
 *   2. COMMANDS (JSON RPC) - POST /api/command
 *   3. DOWNLOAD - GET /api/download/{target}?zip_mode=true
 * 
 * JSON formats:
 *   Legacy: { "parametri": {...}, "files": {...}, "auth": {...} }
 *   Command: { "comando": "save|exit|restart|reboot|poweroff|exec", "target": "...", "payload": {...} }
 */

import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.*;
import java.util.concurrent.TimeUnit;
import com.google.gson.*;

public class ntwebsrv_client {
    
    private static final String DEFAULT_BASE_URL = "http://localhost:8000";
    private static final int DEFAULT_TIMEOUT = 30;
    private static final String BOUNDARY = "----ntwebsrvBoundary" + System.currentTimeMillis();
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    
    private static boolean verbose = false;
    private static boolean italian = false;
    private static boolean downloadMode = false;
    private static boolean zipMode = false;
    private static String downloadTarget = "";
    private static String outputFile = "";
    
    public static void main(String[] args) {
        // Detect language
        String lang = System.getProperty("user.language", "en");
        italian = lang.startsWith("it");
        
        // Parse arguments
        String jsonFile = null;
        String baseUrl = DEFAULT_BASE_URL;
        String key = "";
        String keyhashBase = "";
        int timeout = DEFAULT_TIMEOUT;
        
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "-u", "--url":
                    if (i + 1 < args.length) baseUrl = args[++i];
                    break;
                case "-k", "--key":
                    if (i + 1 < args.length) key = args[++i];
                    break;
                case "-kh", "--keyhash":
                    if (i + 1 < args.length) keyhashBase = args[++i];
                    break;
                case "-t", "--timeout":
                    if (i + 1 < args.length) timeout = Integer.parseInt(args[++i]);
                    break;
                case "-v", "--verbose":
                    verbose = true;
                    break;
                case "-h", "--help":
                    printHelp();
                    return;
                case "--download":
                    if (i + 1 < args.length) {
                        downloadMode = true;
                        downloadTarget = args[++i];
                    }
                    break;
                case "--zip":
                    zipMode = true;
                    break;
                case "-o", "--output":
                    if (i + 1 < args.length) outputFile = args[++i];
                    break;
                default:
                    if (!args[i].startsWith("-")) {
                        if (jsonFile == null) jsonFile = args[i];
                        else { error("Multiple JSON files specified"); return; }
                    } else {
                        error("Unknown option: " + args[i]);
                        return;
                    }
            }
        }
        
        // Download mode doesn't require JSON file
        if (!downloadMode && jsonFile == null) {
            printHelp();
            error("JSON file required (or use --download)");
            return;
        }
        
        // Build auth header
        Map<String, String> authHeaders = buildAuthHeaders(key, keyhashBase);
        
        if (downloadMode) {
            doDownload(baseUrl, downloadTarget, zipMode, outputFile, authHeaders, timeout);
            return;
        }
        
        // Read and parse JSON
        JsonObject data;
        try {
            String content = Files.readString(Path.of(jsonFile), StandardCharsets.UTF_8);
            data = JsonParser.parseString(content).getAsJsonObject();
        } catch (Exception e) {
            error("Failed to read/parse JSON: " + e.getMessage());
            return;
        }
        
        // Check if command mode (has "comando" field)
        boolean isCommandMode = data.has("comando");
        
        // Add JSON auth if no CLI auth provided
        if (authHeaders.isEmpty()) {
            JsonObject auth = data.has("auth") ? data.getAsJsonObject("auth") : new JsonObject();
            String jsonKey = auth.has("key") ? auth.get("key").getAsString() : "";
            String jsonKhBase = auth.has("keyhash") ? auth.get("keyhash").getAsString() : "";
            authHeaders = buildAuthHeaders(jsonKey, jsonKhBase);
        }
        
        if (isCommandMode) {
            doCommand(baseUrl, data, authHeaders, timeout);
        } else {
            doLegacyUpload(baseUrl, data, authHeaders, timeout);
        }
    }
    
    // ========================================================================
    // AUTHENTICATION
    // ========================================================================
    
    private static Map<String, String> buildAuthHeaders(String key, String keyhashBase) {
        Map<String, String> headers = new HashMap<>();
        if (!keyhashBase.isEmpty()) {
            int day = LocalDate.now().getDayOfMonth();
            headers.put("X-API-Key", sha256Hex(keyhashBase + day));
            log("[INFO] Using _kh authentication");
        } else if (!key.isEmpty()) {
            headers.put("X-API-Key", key);
            log("[INFO] Using _k authentication");
        }
        return headers;
    }
    
    private static String sha256Hex(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte b : hash) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (Exception e) {
            throw new RuntimeException("SHA-256 failed", e);
        }
    }
    
    // ========================================================================
    // MODE 1: LEGACY UPLOAD (multipart)
    // ========================================================================
    
    private static void doLegacyUpload(String baseUrl, JsonObject data, Map<String, String> authHeaders, int timeout) {
        String url = baseUrl.replaceAll("/+$", "") + "/ricevi";
        
        // Extract sections
        JsonObject parametri = data.has("parametri") ? data.getAsJsonObject("parametri") : new JsonObject();
        JsonObject files = data.has("files") ? data.getAsJsonObject("files") : new JsonObject();
        
        // Verify files exist
        Map<String, Path> filePaths = new HashMap<>();
        for (Map.Entry<String, JsonElement> entry : files.entrySet()) {
            String field = entry.getKey();
            String pathStr = entry.getValue().getAsString();
            Path path = Path.of(pathStr).toAbsolutePath().normalize();
            if (Files.isRegularFile(path)) {
                filePaths.put(field, path);
                log("[INFO] File verified: " + field + " -> " + path);
            } else {
                error("Missing file: " + field + " -> " + pathStr);
                return;
            }
        }
        
        // Build multipart body
        ByteArrayOutputStream bodyStream = new ByteArrayOutputStream();
        try (PrintWriter writer = new PrintWriter(new OutputStreamWriter(bodyStream, StandardCharsets.UTF_8), true)) {
            // Add parametri fields
            for (Map.Entry<String, JsonElement> entry : parametri.entrySet()) {
                writeFormField(writer, entry.getKey(), entry.getValue().getAsString());
            }
            
            // Add legacy auth as form fields (from JSON auth, since header auth already set)
            JsonObject auth = data.has("auth") ? data.getAsJsonObject("auth") : new JsonObject();
            String authKey = auth.has("key") ? auth.get("key").getAsString() : "";
            String authKhBase = auth.has("keyhash") ? auth.get("keyhash").getAsString() : "";
            if (!authKhBase.isEmpty()) {
                int day = LocalDate.now().getDayOfMonth();
                writeFormField(writer, "_kh", sha256Hex(authKhBase + day));
            } else if (!authKey.isEmpty()) {
                writeFormField(writer, "_k", authKey);
            }
            
            // Add files
            for (Map.Entry<String, Path> entry : filePaths.entrySet()) {
                writeFileField(writer, bodyStream, entry.getKey(), entry.getValue());
            }
            
            // End boundary
            writer.append("--").append(BOUNDARY).append("--").append("\r\n");
        } catch (IOException e) {
            error("Failed to build request body: " + e.getMessage());
            return;
        }
        
        byte[] bodyBytes = bodyStream.toByteArray();
        
        // Send request
        log("[INFO] Uploading to " + url);
        log("[INFO] Form fields: " + (parametri.size() + filePaths.size()) + ", Files: " + filePaths.size());
        
        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(timeout))
            .build();
        
        String contentType = "multipart/form-data; boundary=" + BOUNDARY;
        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Content-Type", contentType)
            .timeout(java.time.Duration.ofSeconds(timeout))
            .POST(HttpRequest.BodyPublishers.ofByteArray(bodyBytes));
        
        // Add auth headers
        for (Map.Entry<String, String> h : authHeaders.entrySet()) {
            requestBuilder.header(h.getKey(), h.getValue());
        }
        
        HttpRequest request = requestBuilder.build();
        
        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            handleResponse(response);
        } catch (java.net.http.HttpTimeoutException e) {
            error("Timeout (" + timeout + "s)");
        } catch (IOException e) {
            if (e.getCause() instanceof java.net.ConnectException) {
                error("Connection failed (server unreachable)");
            } else {
                error("Request failed: " + e.getMessage());
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            error("Request interrupted");
        }
    }
    
    // ========================================================================
    // MODE 2: COMMANDS (JSON RPC)
    // ========================================================================
    
    private static void doCommand(String baseUrl, JsonObject command, Map<String, String> authHeaders, int timeout) {
        String url = baseUrl.replaceAll("/+$", "") + "/api/command";
        String comando = command.get("comando").getAsString();
        
        log("[INFO] Sending command '" + comando + "' to " + url);
        
        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(timeout))
            .build();
        
        String jsonBody = GSON.toJson(command);
        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Content-Type", "application/json")
            .timeout(java.time.Duration.ofSeconds(timeout))
            .POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8));
        
        for (Map.Entry<String, String> h : authHeaders.entrySet()) {
            requestBuilder.header(h.getKey(), h.getValue());
        }
        
        HttpRequest request = requestBuilder.build();
        
        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            handleResponse(response);
        } catch (java.net.http.HttpTimeoutException e) {
            error("Timeout (" + timeout + "s)");
        } catch (IOException e) {
            if (e.getCause() instanceof java.net.ConnectException) {
                error("Connection failed (server unreachable)");
            } else {
                error("Request failed: " + e.getMessage());
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            error("Request interrupted");
        }
    }
    
    // ========================================================================
    // MODE 3: DOWNLOAD
    // ========================================================================
    
    private static void doDownload(String baseUrl, String target, boolean zip, String outputFile, Map<String, String> authHeaders, int timeout) {
        String url = baseUrl.replaceAll("/+$", "") + "/api/download/" + target;
        if (zip) url += "?zip_mode=true";
        
        log("[INFO] Downloading from " + url);
        
        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(timeout))
            .build();
        
        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .timeout(java.time.Duration.ofSeconds(timeout))
            .GET();
        
        for (Map.Entry<String, String> h : authHeaders.entrySet()) {
            requestBuilder.header(h.getKey(), h.getValue());
        }
        
        HttpRequest request = requestBuilder.build();
        
        try {
            HttpResponse<byte[]> response = client.send(request, HttpResponse.BodyHandlers.ofByteArray());
            int statusCode = response.statusCode();
            byte[] body = response.body();
            
            log("[INFO] HTTP Status: " + statusCode);
            
            if (statusCode == 200) {
                String filename = outputFile;
                if (filename.isEmpty()) {
                    // Try to get filename from Content-Disposition
                    String cd = response.headers().firstValue("Content-Disposition").orElse("");
                    if (cd.contains("filename=")) {
                        filename = cd.split("filename=")[1].replace("\"", "").trim();
                    } else {
                        filename = "download_" + LocalDate.now() + "_" + System.currentTimeMillis();
                    }
                }
                
                Files.write(Path.of(filename), body);
                System.out.println((italian ? "SUCCESSO: Scaricato come " : "SUCCESS: Downloaded as ") + filename);
            } else {
                String errorBody = new String(body, StandardCharsets.UTF_8);
                System.err.println((italian ? "FALLITO (HTTP " : "FAILED (HTTP ") + statusCode + ")");
                try {
                    JsonElement parsed = JsonParser.parseString(errorBody);
                    System.err.println(GSON.toJson(parsed));
                } catch (Exception e) {
                    System.err.println(errorBody);
                }
                System.exit(1);
            }
        } catch (java.net.http.HttpTimeoutException e) {
            error("Timeout (" + timeout + "s)");
        } catch (IOException e) {
            if (e.getCause() instanceof java.net.ConnectException) {
                error("Connection failed (server unreachable)");
            } else {
                error("Request failed: " + e.getMessage());
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            error("Request interrupted");
        }
    }
    
    // ========================================================================
    // HELPERS
    // ========================================================================
    
    private static void handleResponse(HttpResponse<String> response) {
        int statusCode = response.statusCode();
        String responseBody = response.body();
        
        log("[INFO] HTTP Status: " + statusCode);
        
        if (statusCode == 200) {
            System.out.println(italian ? "SUCCESSO" : "SUCCESS");
            try {
                JsonElement parsed = JsonParser.parseString(responseBody);
                System.out.println(GSON.toJson(parsed));
            } catch (Exception e) {
                System.out.println(responseBody);
            }
        } else {
            System.err.println((italian ? "FALLITO (HTTP " : "FAILED (HTTP ") + statusCode + ")");
            try {
                JsonElement parsed = JsonParser.parseString(responseBody);
                System.err.println(GSON.toJson(parsed));
            } catch (Exception e) {
                System.err.println(responseBody);
            }
            System.exit(1);
        }
    }
    
    private static void writeFormField(PrintWriter writer, String name, String value) {
        writer.append("--").append(BOUNDARY).append("\r\n");
        writer.append("Content-Disposition: form-data; name=\"").append(name).append("\"\r\n");
        writer.append("\r\n");
        writer.append(value).append("\r\n");
    }
    
    private static void writeFileField(PrintWriter writer, ByteArrayOutputStream bodyStream, String fieldName, Path filePath) throws IOException {
        String fileName = filePath.getFileName().toString();
        byte[] fileBytes = Files.readAllBytes(filePath);
        
        writer.append("--").append(BOUNDARY).append("\r\n");
        writer.append("Content-Disposition: form-data; name=\"").append(fieldName).append("\"; filename=\"").append(fileName).append("\"\r\n");
        writer.append("Content-Type: application/octet-stream\r\n");
        writer.append("\r\n");
        writer.flush();
        
        bodyStream.write(fileBytes);
        bodyStream.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }
    
    private static void log(String msg) {
        if (verbose) System.out.println(msg);
    }
    
    private static void error(String msg) {
        System.err.println((italian ? "ERRORE: " : "ERROR: ") + msg);
    }
    
    private static void printHelp() {
        if (italian) {
            System.out.println("""
                ntwebsrv_client.java - Client Java per ntwebsrv (Automation Agent)
                
                USO:
                    java ntwebsrv_client [opzioni] FILE_JSON           # Upload/Comandi
                    java ntwebsrv_client --download TARGET [opzioni]   # Download
                
                OPZIONI COMUNI:
                    -u, --url URL        URL base server (default: http://localhost:8000)
                    -k, --key KEY        Chiave segreta (header X-API-Key)
                    -kh, --keyhash BASE  Segreto base per _kh (SHA256(base + giorno))
                    -t, --timeout SEC    Timeout secondi (default: 30)
                    -v, --verbose        Output dettagliato
                    -h, --help           Questo help
                
                OPZIONI DOWNLOAD:
                    --download TARGET    File/cartella da scaricare (non richiede FILE_JSON)
                    --zip                Zippa cartella al volo (richiede --download)
                    -o, --output FILE    Nome file output (default: dal server)
                
                MODALITÀ 1: LEGACY UPLOAD (multipart) - POST /ricevi
                    JSON con "parametri" e/o "files":
                    {
                      "parametri": { "campo1": "valore1" },
                      "files": { "documento": "percorso/file.pdf" },
                      "auth": { "key": "chiave", "keyhash": "base_secret" }
                    }
                
                MODALITÀ 2: COMANDI (JSON RPC) - POST /api/command
                    JSON con "comando":
                    {"comando": "save", "payload": {...}}
                    {"comando": "exit"}
                    {"comando": "restart"}
                    {"comando": "reboot"}
                    {"comando": "poweroff"}
                    {"comando": "exec", "target": "nome_script"}
                
                MODALITÀ 3: DOWNLOAD - GET /api/download/{target}
                    java ntwebsrv_client --download report.pdf -k "chiave"
                    java ntwebsrv_client --download logs --zip -k "chiave"
                
                AUTENTICAZIONE:
                    - Header X-API-Key: <key|kh>  (o Authorization: Bearer <key|kh>)
                    - "auth.keyhash" nel JSON è il segreto base (NON l'hash). Client calcola _kh = SHA256(keyhash + giorno_corrente)
                    - Opzioni CLI (-k/-kh) sovrascrivono "auth" nel JSON
                
                ESEMPI:
                    # Legacy upload
                    java ntwebsrv_client upload.json -k "mia_chiave" -v
                    
                    # Comandi
                    java ntwebsrv_client cmd_save.json -k "mia_chiave" -v
                    java ntwebsrv_client cmd_exit.json -kh "mio_base_secret"
                    
                    # Download
                    java ntwebsrv_client --download report.pdf -k "mia_chiave"
                    java ntwebsrv_client --download logs --zip -k "mia_chiave"
                """);
        } else {
            System.out.println("""
                ntwebsrv_client.java - Java client for ntwebsrv (Automation Agent)
                
                USAGE:
                    java ntwebsrv_client [options] JSON_FILE           # Upload/Commands
                    java ntwebsrv_client --download TARGET [options]   # Download
                
                COMMON OPTIONS:
                    -u, --url URL        Base server URL (default: http://localhost:8000)
                    -k, --key KEY        Secret key (X-API-Key header)
                    -kh, --keyhash BASE  Base secret for _kh (SHA256(base + day))
                    -t, --timeout SEC    Timeout seconds (default: 30)
                    -v, --verbose        Verbose output
                    -h, --help           This help
                
                DOWNLOAD OPTIONS:
                    --download TARGET    File/folder to download (no JSON_FILE required)
                    --zip                Zip folder on-the-fly (requires --download)
                    -o, --output FILE    Output filename (default: from server)
                
                MODE 1: LEGACY UPLOAD (multipart) - POST /ricevi
                    JSON with "parametri" and/or "files":
                    {
                      "parametri": { "field1": "value1" },
                      "files": { "document": "path/file.pdf" },
                      "auth": { "key": "secret", "keyhash": "base_secret" }
                    }
                
                MODE 2: COMMANDS (JSON RPC) - POST /api/command
                    JSON with "comando":
                    {"comando": "save", "payload": {...}}
                    {"comando": "exit"}
                    {"comando": "restart"}
                    {"comando": "reboot"}
                    {"comando": "poweroff"}
                    {"comando": "exec", "target": "script_name"}
                
                MODE 3: DOWNLOAD - GET /api/download/{target}
                    java ntwebsrv_client --download report.pdf -k "secret"
                    java ntwebsrv_client --download logs --zip -k "secret"
                
                AUTHENTICATION:
                    - Header X-API-Key: <key|kh>  (or Authorization: Bearer <key|kh>)
                    - "auth.keyhash" in JSON is base secret (NOT hash). Client calculates _kh = SHA256(keyhash + day)
                    - CLI options (-k/-kh) override JSON "auth"
                
                EXAMPLES:
                    # Legacy upload
                    java ntwebsrv_client upload.json -k "my_key" -v
                    
                    # Commands
                    java ntwebsrv_client cmd_save.json -k "my_key" -v
                    java ntwebsrv_client cmd_exit.json -kh "my_base_secret"
                    
                    # Download
                    java ntwebsrv_client --download report.pdf -k "my_key"
                    java ntwebsrv_client --download logs --zip -k "my_key"
                """);
        }
    }
}