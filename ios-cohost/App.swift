import UIKit
import Foundation
import MadDB

@objc(MadCohostDriver)
public final class MadCohostDriver: NSObject {
    private static let serial = DispatchQueue(label: "mad.cohost.sample")
    private static let lock = NSLock()
    private static var used = false

    // The sample accepts one fixed scenario. It cannot accumulate pending work
    // or replay a failed native cleanup. The UI and hosted XCTest use this same ingress.
    @objc(run:) public static func run(_ completion: @escaping (Bool) -> Void) {
        lock.lock()
        let available = !used
        used = true
        lock.unlock()
        guard available else { DispatchQueue.main.async { completion(false) }; return }
        serial.async {
            let success = exercise()
            DispatchQueue.main.async { completion(success) }
        }
    }

    private static func exercise() -> Bool {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let wal = root.appendingPathComponent("observation", isDirectory: true)
        do {
            try fm.createDirectory(at: root, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
            #if COHOST_OBS
            try fm.createDirectory(at: wal, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
            #endif
        } catch { return false }
        #if COHOST_OBS
        let state = wal.path.withCString { mco_open($0) }
        #else
        let state = mco_open(nil)
        #endif
        guard let state else { return false } // Native callback state might need the folder until process exit.
        func report(_ operation: UInt32) -> Bool {
            #if COHOST_OBS
            return mco_db_report(state, operation) == 1
            #else
            return true
            #endif
        }
        let store = root.appendingPathComponent("synthetic.sqlite")
        func operations() throws -> Bool {
            let bytes = Data([0, 42, 255])
            let a = try MadDatabase(fileURL: store, namespace: "sample")
            defer { try? a.close() }
            try a.put("fixed", value: bytes)
            guard report(1), try a.get("fixed") == bytes, report(2), mco_send(state, 1) == 1 else { return false }
            try a.close()
            guard mco_send(state, 2) == 1 else { return false } // DB no longer open.
            let b = try MadDatabase(fileURL: store, namespace: "sample")
            defer { try? b.close() }
            guard mco_close_link(state) == 1, try b.get("fixed") == bytes, report(3) else { return false }
            try b.remove("missing")
            guard report(4), try b.get("missing") == nil else { return false } // Real DB success; policy-excluded event.
            try b.close()
            return true
        }
        let success = (try? operations()) == true
        let stopped = mco_finish(state, success ? 1 : 0) == 1
        guard stopped else { return false }
        do { try fm.removeItem(at: root) }
        catch { return false }
        return success
    }
}

@main final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    private let button = UIButton(type: .system)
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        let controller = UIViewController()
        controller.view.backgroundColor = .systemBackground
        button.setTitle("Run SDK sample", for: .normal)
        button.addTarget(self, action: #selector(runSample), for: .touchUpInside)
        button.translatesAutoresizingMaskIntoConstraints = false
        controller.view.addSubview(button)
        NSLayoutConstraint.activate([button.centerXAnchor.constraint(equalTo: controller.view.centerXAnchor),
                                     button.centerYAnchor.constraint(equalTo: controller.view.centerYAnchor)])
        window.rootViewController = controller
        window.makeKeyAndVisible()
        self.window = window
        return true
    }
    @objc private func runSample() {
        button.isEnabled = false
        MadCohostDriver.run { [weak self] ok in
            self?.button.setTitle(ok ? "Passed" : "Failed", for: .disabled)
        }
    }
}
