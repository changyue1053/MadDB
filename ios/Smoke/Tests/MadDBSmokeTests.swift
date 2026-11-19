import Foundation
import XCTest
import MadDB

final class MadDBSmokeTests: XCTestCase {
    private func assertMadDBError<T>(
        _ expected: MadDBError,
        _ operation: @autoclosure () throws -> T,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertThrowsError(try operation(), file: file, line: line) { error in
            XCTAssertEqual(error as? MadDBError, expected, file: file, line: line)
        }
    }

    func testABIVersionIsOne() {
        XCTAssertEqual(MadDatabase.abiVersion, UInt32(1))
    }

    private func withTemporaryDirectory(_ body: (URL) throws -> Void) throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("MadDB-测试-🧪-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        try body(directory)
    }

    func testUnicodePathKeyBinaryEmptyMissingAndReopen() throws {
        try withTemporaryDirectory { directory in
            let file = directory.appendingPathComponent("数据库-🗃️.sqlite")
            let key = "键🔑\0'\"; DROP TABLE maddb_kv; --"
            let payload = Data([0, 1, 127, 128, 254, 255, 0])
            let first = try MadDatabase(fileURL: file, namespace: "测试.app")
            defer { try? first.close() }
            XCTAssertNil(try first.get("not-present"))
            try first.put(key, value: payload)
            try first.put("empty", value: Data())
            XCTAssertEqual(try first.get(key), payload)
            XCTAssertEqual(try first.get("empty"), Data())
            try first.close()

            let reopened = try MadDatabase(fileURL: file, namespace: "测试.app")
            defer { try? reopened.close() }
            XCTAssertEqual(try reopened.get(key), payload)
            XCTAssertEqual(try reopened.get("empty"), Data())
            try reopened.put(key, value: Data([42]))
            XCTAssertEqual(try reopened.get(key), Data([42]))
            try reopened.remove(key)
            try reopened.remove(key)
            XCTAssertNil(try reopened.get(key))
        }
    }

    func testNamespacesDoNotMixValues() throws {
        try withTemporaryDirectory { directory in
            let file = directory.appendingPathComponent("shared.sqlite")
            let a = try MadDatabase(fileURL: file, namespace: "app.a")
            defer { try? a.close() }
            let b = try MadDatabase(fileURL: file, namespace: "app.b")
            defer { try? b.close() }
            try a.put("same", value: Data([1]))
            XCTAssertNil(try b.get("same"))
            try b.put("same", value: Data([2]))
            try a.remove("same")
            XCTAssertEqual(try b.get("same"), Data([2]))
        }
    }

    func testMemoryDatabasesAreIndependent() throws {
        let a = try MadDatabase.inMemory()
        defer { try? a.close() }
        let b = try MadDatabase.inMemory()
        defer { try? b.close() }
        try a.put("same", value: Data([1]))
        XCTAssertNil(try b.get("same"))
    }

    func testCloseIsIdempotentAndOperationsFailAfterClose() throws {
        let db = try MadDatabase.inMemory()
        try db.close()
        XCTAssertNoThrow(try db.close())
        assertMadDBError(.nativeStatus(-2), try db.get("key"))
        assertMadDBError(.nativeStatus(-2), try db.put("key", value: Data()))
        assertMadDBError(.nativeStatus(-2), try db.remove("key"))
    }

    func testEmptyNamespaceIsRejected() throws {
        assertMadDBError(.nativeStatus(-1), try MadDatabase.inMemory(namespace: ""))
        try withTemporaryDirectory { directory in
            let file = directory.appendingPathComponent("invalid.sqlite")
            assertMadDBError(.nativeStatus(-1), try MadDatabase(fileURL: file, namespace: ""))
        }
    }

    func testStorageAndInvalidDatabaseErrorsAreSurfaced() throws {
        try withTemporaryDirectory { directory in
            let absentParent = directory.appendingPathComponent("absent", isDirectory: true)
                .appendingPathComponent("db.sqlite")
            assertMadDBError(.nativeStatus(-3), try MadDatabase(fileURL: absentParent))
            let corrupt = directory.appendingPathComponent("not-a-database.sqlite")
            let bytes = Data(repeating: 0xA5, count: 4096)
            try bytes.write(to: corrupt)
            assertMadDBError(.nativeStatus(-3), try MadDatabase(fileURL: corrupt))
            XCTAssertEqual(try Data(contentsOf: corrupt), bytes)
        }
    }

    func testOversizedValueIsRejectedWithoutChangingExistingValue() throws {
        let db = try MadDatabase.inMemory()
        defer { try? db.close() }
        let original = Data([1, 2, 3])
        try db.put("size-limit", value: original)
        let oversized = Data(repeating: 0xA5, count: 16 * 1024 * 1024 + 1)
        assertMadDBError(.valueTooLarge, try db.put("size-limit", value: oversized))
        XCTAssertEqual(try db.get("size-limit"), original)
    }

    func testFutureSchemaIsRejectedWithoutChangingFile() throws {
        try withTemporaryDirectory { directory in
            let file = directory.appendingPathComponent("future-schema.sqlite")
            let db = try MadDatabase(fileURL: file)
            defer { try? db.close() }
            try db.put("preserved", value: Data([42]))
            try db.close()

            var bytes = try Data(contentsOf: file)
            XCTAssertGreaterThanOrEqual(bytes.count, 100)
            guard bytes.count >= 100 else { return }
            XCTAssertEqual(bytes.prefix(16), Data("SQLite format 3\0".utf8))
            // SQLite user_version is a 32-bit big-endian field at header offset 60.
            // Modify a closed, valid MadDB file without a system SQLite dependency.
            bytes.replaceSubrange(60..<64, with: [UInt8(0), 0, 0, 99])
            try bytes.write(to: file)
            assertMadDBError(.nativeStatus(-4), try MadDatabase(fileURL: file))
            XCTAssertEqual(try Data(contentsOf: file), bytes)
        }
    }
}
