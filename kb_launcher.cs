using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace KbLauncher
{
    class Program
    {
        // ---- 打包时烧入的路径（可自行修改后重新编译）----
        const string CODE_DIR = @"e:\思考\社会思考\code";
        const string PYTHON = @"D:\Coding\envs\image\python.exe";
        const string BACKEND_LOG = @"e:\思考\社会思考\code\_kb_launcher_backend.log";
        const int BACKEND_PORT = 8000;
        const int NEO4J_PORT = 7687;
        const string NEO4J_HOME = @"E:\Coding\Neo4j\PersonalKG";
        const string NEO4J_LOG = @"e:\思考\社会思考\code\_kb_launcher_neo4j.log";
        const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public IntPtr MinimumWorkingSetSize;
            public IntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public IntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IO_COUNTERS
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public IntPtr ProcessMemoryLimit;
            public IntPtr JobMemoryLimit;
            public IntPtr PeakProcessMemoryUsed;
            public IntPtr PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetInformationJobObject(IntPtr hJob, int JobObjectInformationClass,
            IntPtr lpJobObjectInformation, uint cbJobObjectInformationLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr hObject);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetConsoleTitle(string lpConsoleTitle);

        static int Main()
        {
            Console.OutputEncoding = Encoding.UTF8;
            SetConsoleTitle("个人知识库");
            Line("========================================");
            Line("         个人知识库 一键启动");
            Line("========================================");

            if (!Directory.Exists(CODE_DIR))
            {
                Line("[x] 未找到代码目录: " + CODE_DIR);
                Pause();
                return 1;
            }

            // 创建 Job Object：Neo4j 与后端都加入其中，关闭窗口即全部停止
            IntPtr job = CreateJobObject(IntPtr.Zero, null);
            if (job == IntPtr.Zero)
            {
                Line("[x] 创建 Job Object 失败 (错误码 " + Marshal.GetLastWin32Error() + ")");
                Pause();
                return 1;
            }
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION jinfo = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            jinfo.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            IntPtr jptr = Marshal.AllocHGlobal(Marshal.SizeOf(jinfo));
            Marshal.StructureToPtr(jinfo, jptr, false);
            bool setOk = SetInformationJobObject(job, 9, jptr, (uint)Marshal.SizeOf(jinfo));
            Marshal.FreeHGlobal(jptr);
            if (!setOk)
            {
                Line("[x] 设置 Job Object 失败 (错误码 " + Marshal.GetLastWin32Error() + ")");
                CloseHandle(job);
                Pause();
                return 1;
            }

            Process neo4j = null;

            // [1/3] Neo4j：未在线则自动启动
            Line("");
            Line("[1/3] 检查 Neo4j (7687) ...");
            if (PortOpen(NEO4J_PORT))
            {
                Line("  Neo4j 在线");
            }
            else
            {
                Line("  Neo4j 未在线，正在自动启动 ...");
                neo4j = StartNeo4j(job);
                if (neo4j == null)
                {
                    CloseHandle(job);
                    Pause();
                    return 1;
                }
                if (!WaitPort(NEO4J_PORT, 60))
                {
                    Line("[x] Neo4j 启动超时(60s)，请查看日志:");
                    Line("    " + NEO4J_LOG);
                    TryKill(neo4j);
                    CloseHandle(job);
                    Pause();
                    return 1;
                }
                Line("  Neo4j 已就绪 (PID " + neo4j.Id + ")");
            }

            // [2/3] 清理旧端口
            Line("");
            Line("[2/3] 检查端口占用 ...");
            KillPort(BACKEND_PORT);
            Line("  后端(8000) 端口空闲");

            // [3/3] 启动后端
            Line("");
            Line("[3/3] 启动后端服务 (8000) ...");
            if (!File.Exists(PYTHON))
            {
                Line("[x] 未找到 Python: " + PYTHON);
                Pause();
                return 1;
            }

            Process backend = StartBackend();
            if (backend == null)
            {
                CloseHandle(job);
                Pause();
                return 1;
            }

            if (!AssignProcessToJobObject(job, backend.Handle))
            {
                Line("  [!!] AssignProcessToJobObject 失败 (错误码 " + Marshal.GetLastWin32Error() + ")，");
                Line("       关闭窗口时后端可能无法自动停止");
            }
            Line("  后端已启动 PID " + backend.Id);

            if (!WaitPort(BACKEND_PORT, 25))
            {
                Line("[x] 后端启动超时，请查看日志:");
                Line("    " + BACKEND_LOG);
                TryKill(backend);
                CloseHandle(job);
                Pause();
                return 1;
            }
            Line("  后端就绪: http://localhost:8000");

            try
            {
                Process.Start("http://localhost:8000");
            }
            catch (Exception) { }

            Line("");
            Line("  知识库已启动，浏览器已打开。");
            Line("  保持本窗口运行；关闭窗口或按 Ctrl+C 即可停止全部服务。");
            Line("----------------------------------------");

            bool stopping = false;
            Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e)
            {
                if (!stopping)
                {
                    stopping = true;
                    Line("");
                    Line("收到退出请求，正在停止服务...");
                    TryKill(neo4j);
                    TryKill(backend);
                    CloseHandle(job);
                    Line("服务已全部停止，窗口可关闭。");
                }
            };

            // 阻塞直到窗口关闭（点 X）或 Ctrl+C
            while (true)
            {
                Thread.Sleep(500);
                if (stopping) break;
            }
            return 0;
        }

        static Process StartNeo4j(IntPtr job)
        {
            try
            {
                string bat = Path.Combine(NEO4J_HOME, "bin", "neo4j.bat");
                if (!File.Exists(bat))
                {
                    Line("[x] 未找到 Neo4j 启动脚本: " + bat);
                    return null;
                }
                Process p = new Process();
                p.StartInfo.FileName = "cmd.exe";
                p.StartInfo.Arguments = "/c \"\"" + bat + "\" console\"";
                p.StartInfo.WorkingDirectory = NEO4J_HOME;
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.StartInfo.RedirectStandardOutput = true;
                p.StartInfo.RedirectStandardError = true;
                p.StartInfo.StandardOutputEncoding = Encoding.UTF8;
                p.StartInfo.StandardErrorEncoding = Encoding.UTF8;
                p.StartInfo.EnvironmentVariables["NEO4J_HOME"] = NEO4J_HOME;
                p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e)
                {
                    if (e.Data != null) AppendNeo4jLog(e.Data);
                };
                p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e)
                {
                    if (e.Data != null) AppendNeo4jLog(e.Data);
                };
                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();

                if (!AssignProcessToJobObject(job, p.Handle))
                {
                    Line("  [!!] Neo4j 加入 Job Object 失败 (错误码 " + Marshal.GetLastWin32Error() + ")，");
                    Line("       关闭窗口时数据库可能无法自动停止");
                }
                return p;
            }
            catch (Exception ex)
            {
                Line("[x] 启动 Neo4j 失败: " + ex.Message);
                return null;
            }
        }

        static void AppendNeo4jLog(string line)
        {
            try
            {
                File.AppendAllText(NEO4J_LOG, line + "\r\n", Encoding.UTF8);
            }
            catch (Exception) { }
        }

        static Process StartBackend()
        {
            try
            {
                Process p = new Process();
                p.StartInfo.FileName = PYTHON;
                p.StartInfo.Arguments = "-m uvicorn backend.main:app --port " + BACKEND_PORT;
                p.StartInfo.WorkingDirectory = CODE_DIR;
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.StartInfo.RedirectStandardOutput = true;
                p.StartInfo.RedirectStandardError = true;
                p.StartInfo.StandardOutputEncoding = Encoding.UTF8;
                p.StartInfo.StandardErrorEncoding = Encoding.UTF8;
                p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e)
                {
                    if (e.Data != null) AppendLog(e.Data);
                };
                p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e)
                {
                    if (e.Data != null) AppendLog(e.Data);
                };
                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                return p;
            }
            catch (Exception ex)
            {
                Line("[x] 启动后端失败: " + ex.Message);
                return null;
            }
        }

        static void AppendLog(string line)
        {
            try
            {
                File.AppendAllText(BACKEND_LOG, line + "\r\n", Encoding.UTF8);
            }
            catch (Exception) { }
        }

        static void TryKill(Process p)
        {
            try
            {
                if (p != null && !p.HasExited)
                {
                    p.Kill();
                    p.WaitForExit(3000);
                }
            }
            catch (Exception) { }
        }

        static bool PortOpen(int port)
        {
            try
            {
                using (TcpClient c = new TcpClient())
                {
                    var task = c.ConnectAsync("127.0.0.1", port);
                    return task.Wait(1000);
                }
            }
            catch (Exception) { return false; }
        }

        static bool WaitPort(int port, int seconds)
        {
            for (int i = 0; i < seconds * 2; i++)
            {
                if (PortOpen(port)) return true;
                Thread.Sleep(500);
            }
            return false;
        }

        static void KillPort(int port)
        {
            try
            {
                Process p = new Process();
                p.StartInfo.FileName = "netstat";
                p.StartInfo.Arguments = "-ano";
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.StartInfo.RedirectStandardOutput = true;
                p.Start();
                string outText = p.StandardOutput.ReadToEnd();
                p.WaitForExit();
                string marker = ":" + port;
                foreach (string line in outText.Split('\n'))
                {
                    if (line.IndexOf("LISTENING", StringComparison.OrdinalIgnoreCase) < 0) continue;
                    int idx = line.IndexOf(marker);
                    if (idx < 0) continue;
                    int pid = -1;
                    string[] parts = line.Trim().Split(new char[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length >= 5)
                    {
                        int.TryParse(parts[parts.Length - 1], out pid);
                    }
                    if (pid > 0)
                    {
                        Line("  后端(8000) 端口被旧进程 PID " + pid + " 占用，正在停止...");
                        KillPid(pid);
                        Thread.Sleep(1000);
                    }
                }
            }
            catch (Exception) { }
        }

        static void KillPid(int pid)
        {
            try
            {
                Process p = new Process();
                p.StartInfo.FileName = "taskkill";
                p.StartInfo.Arguments = "/F /T /PID " + pid;
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.Start();
                p.WaitForExit(3000);
            }
            catch (Exception) { }
        }

        static void Line(string msg)
        {
            Console.WriteLine(msg);
        }

        static void Pause()
        {
            try { Console.WriteLine(); Console.WriteLine("按任意键退出..."); Console.ReadKey(true); }
            catch (Exception) { }
        }
    }
}
