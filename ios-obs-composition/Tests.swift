import Foundation
import XCTest
import MadDB

final class MadDBObsCompositionTests: XCTestCase {
    func testSQLitePrivateEventsDrain() throws {
        #if !targetEnvironment(simulator) || !arch(arm64)
        XCTFail("Composition runtime requires ARM64 iOS simulator")
        return
        #endif
        let path = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: path, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        defer { try? FileManager.default.removeItem(at: path) }
        let state = path.path.withCString { maddb_test_obs_begin($0) }
        let observer = try XCTUnwrap(state)
        var finished = false
        defer { if !finished { _ = maddb_test_obs_finish(observer) } }
        let db = try MadDatabase.inMemory(namespace: "synthetic")
        defer { try? db.close() }
        let value = Data([0, 7, 255])
        try db.put("k", value: value)
        XCTAssertEqual(maddb_test_obs_report(observer, 1), 1)
        let present = try db.get("k")
        XCTAssertEqual(present, value)
        if present == value { XCTAssertEqual(maddb_test_obs_report(observer, 2), 1) }
        let missing = try db.get("absent")
        XCTAssertNil(missing)
        if missing == nil { XCTAssertEqual(maddb_test_obs_report(observer, 3), 1) }
        try db.close()
        finished = true // finish consumes state on success; never retry the pointer.
        XCTAssertEqual(maddb_test_obs_finish(observer), 1)
    }
}
