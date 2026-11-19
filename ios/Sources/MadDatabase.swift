import Foundation
@_implementationOnly import CMadDB

/// Stable C status values are retained rather than conflating missing data and errors.
public enum MadDBError: Error, Equatable {
    case nativeStatus(Int32)
    case valueTooLarge
    case changedDuringRead
}

/// Synchronous, plaintext SQLite. Call away from the UI thread.
/// Operations and close are serialized per instance. This preview does not declare
/// Sendable; callers must respect their Swift isolation boundaries.
public final class MadDatabase {
    private let lock = NSLock()
    private var handle: UInt64
    private static let maxValueBytes = 16 * 1024 * 1024

    private init(handle: UInt64) { self.handle = handle }

    public convenience init(fileURL: URL, namespace: String = "default") throws {
        guard fileURL.isFileURL else { throw MadDBError.nativeStatus(-1) }
        let path = Array(fileURL.path.utf8)
        let ns = Array(namespace.utf8)
        var token: UInt64 = 0
        let status = path.withUnsafeBufferPointer { p in
            ns.withUnsafeBufferPointer { n in
                maddb_open(p.baseAddress, p.count, n.baseAddress, n.count, &token)
            }
        }
        try Self.check(status)
        self.init(handle: token)
    }

    public static func inMemory(namespace: String = "default") throws -> MadDatabase {
        let ns = Array(namespace.utf8)
        var token: UInt64 = 0
        let status = ns.withUnsafeBufferPointer {
            maddb_open_memory($0.baseAddress, $0.count, &token)
        }
        try check(status)
        return MadDatabase(handle: token)
    }

    public static var abiVersion: UInt32 { maddb_abi_version() }

    public func put(_ key: String, value: Data) throws {
        guard value.count <= Self.maxValueBytes else { throw MadDBError.valueTooLarge }
        try locked { token in
            let bytes = Array(key.utf8)
            let status = bytes.withUnsafeBufferPointer { k in
                value.withUnsafeBytes { v in
                    maddb_put(token, k.baseAddress, k.count,
                              v.bindMemory(to: UInt8.self).baseAddress, v.count)
                }
            }
            try Self.check(status)
        }
    }

    /// nil is absent; Data() is a present empty value. Copies into caller-owned
    /// storage. External writers may change data between probe and copy; retries
    /// are bounded and do not promise a read snapshot across those calls.
    public func get(_ key: String) throws -> Data? {
        try locked { token in
            let bytes = Array(key.utf8)
            return try bytes.withUnsafeBufferPointer { k in
                for _ in 0..<3 {
                    var needed = 0
                    let probe = maddb_get(token, k.baseAddress, k.count, nil, 0, &needed)
                    if probe == 1 { return nil }
                    if probe == 0 { return Data() }
                    guard probe == 2 else { throw MadDBError.nativeStatus(probe) }
                    guard needed <= Self.maxValueBytes else { throw MadDBError.valueTooLarge }
                    var result = Data(count: needed)
                    var actual = 0
                    let status = result.withUnsafeMutableBytes { buffer in
                        maddb_get(token, k.baseAddress, k.count,
                                  buffer.bindMemory(to: UInt8.self).baseAddress,
                                  buffer.count, &actual)
                    }
                    if status == 1 { return nil }
                    if status == 2 { continue }
                    try Self.check(status)
                    result.count = actual
                    return result
                }
                throw MadDBError.changedDuringRead
            }
        }
    }

    public func remove(_ key: String) throws {
        try locked { token in
            let bytes = Array(key.utf8)
            try bytes.withUnsafeBufferPointer {
                try Self.check(maddb_remove(token, $0.baseAddress, $0.count))
            }
        }
    }

    /// Idempotent at the Swift layer. Calls after close report INVALID_HANDLE (-2).
    /// Token is consumed even if native close reports an error; never retry a token.
    public func close() throws {
        lock.lock(); defer { lock.unlock() }
        guard handle != 0 else { return }
        let token = handle
        handle = 0
        try Self.check(maddb_close(token))
    }

    deinit { if handle != 0 { _ = maddb_close(handle) } }

    private func locked<T>(_ body: (UInt64) throws -> T) throws -> T {
        lock.lock(); defer { lock.unlock() }
        guard handle != 0 else { throw MadDBError.nativeStatus(-2) }
        return try body(handle)
    }

    private static func check(_ status: Int32) throws {
        guard status == 0 else { throw MadDBError.nativeStatus(status) }
    }
}
