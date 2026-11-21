import Foundation
import MadDB
import UIKit

@objc(MadDualSQLiteDriver)
public final class MadDualSQLiteDriver: NSObject {
    private static let serial = DispatchQueue(label: "mad.dual.storage.fixture")

    @objc(run:) public static func run(_ completion: @escaping (Bool) -> Void) {
        serial.async {
            let ok = exercise()
            DispatchQueue.main.async { completion(ok) }
        }
    }

    private static func exercise() -> Bool {
        #if !targetEnvironment(simulator) || !arch(arm64)
        #error("Requires ARM64 iOS Simulator")
        #endif
        let version = ProcessInfo.processInfo.operatingSystemVersion
        guard version.majorVersion == 26 && version.minorVersion == 2, MadDatabase.abiVersion == 1 else { return false }
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        do {
            try fm.createDirectory(at: root, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        } catch { return false }
        let success = (try? scenario(root, fm)) == true
        do { try fm.removeItem(at: root) } catch { return false }
        return success
    }

    private static func scenario(_ root: URL, _ fm: FileManager) throws -> Bool {
        let dbDir = root.appendingPathComponent("db", isDirectory: true)
        let journalDir = root.appendingPathComponent("journal", isDirectory: true)
        let dbFile = dbDir.appendingPathComponent("store.sqlite")
        let journalFile = journalDir.appendingPathComponent("store.sqlite")
        for dir in [dbDir, journalDir] {
            try fm.createDirectory(at: dir, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        }
        let key = "fixed"
        let seed = Data([0, 19, 255])
        let updated = Data([0, 47, 254])
        var db = try MadDatabase(fileURL: dbFile, namespace: "fixture")
        var journal = journalFile.path.withCString { ds_journal_open($0) }
        defer { try? db.close(); ds_journal_close(journal) }
        guard let firstJournal = journal else { return false }

        guard try db.get(key) == nil, ds_journal_put(firstJournal, 11),
              ds_journal_value(firstJournal, 11) else { return false }
        try db.put(key, value: seed)
        guard try db.get(key) == seed, dbFile.path.withCString({ first in
            journalFile.path.withCString { ds_distinct_regular_files(first, $0) }
        }) else { return false }

        // Journal stays live, commits and verifies another value while MadDB is closed.
        try db.close()
        guard ds_journal_put(firstJournal, 37), ds_journal_value(firstJournal, 37) else { return false }
        db = try MadDatabase(fileURL: dbFile, namespace: "fixture")
        guard try db.get(key) == seed else { return false }

        // MadDB stays live and commits while Journal is closed. Reopen the
        // Journal and make a further change while the reopened MadDB is live.
        ds_journal_close(firstJournal)
        journal = nil
        try db.put(key, value: updated)
        guard try db.get(key) == updated else { return false }
        journal = journalFile.path.withCString { ds_journal_open($0) }
        guard let secondJournal = journal, ds_journal_value(secondJournal, 37),
              ds_journal_put(secondJournal, 63), ds_journal_value(secondJournal, 63),
              try db.get(key) == updated else { return false }

        try db.close()
        ds_journal_close(secondJournal)
        journal = nil
        db = try MadDatabase(fileURL: dbFile, namespace: "fixture")
        journal = journalFile.path.withCString { ds_journal_open($0) }
        guard let finalJournal = journal, ds_journal_value(finalJournal, 63),
              try db.get(key) == updated, dbFile.path.withCString({ first in
                  journalFile.path.withCString { ds_distinct_regular_files(first, $0) }
              }) else { return false }
        try db.close()
        ds_journal_close(finalJournal)
        journal = nil
        return true
    }
}

@main final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = UIViewController()
        window.makeKeyAndVisible()
        self.window = window
        return true
    }
}
